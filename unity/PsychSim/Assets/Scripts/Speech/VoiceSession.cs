using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace Rapport.Speech
{
    public enum VoiceState { Off, Listening, Hearing, Thinking, Speaking }

    /// <summary>
    /// Client for the service's voice loop (server/patient-service/PROTOCOL.md): streams 16 kHz mono PCM16 microphone audio to
    /// ws://.../session, plays the patient's 24 kHz PCM as it arrives (one streaming AudioClip on the lip-synced source) and raises
    /// the JSON events on the main thread. Push-to-talk by default (an open mic beside speakers hears the patient); hands-free (service VAD) and typed text go over the same socket.
    /// Audio stays in memory; nothing is written to disk.
    /// </summary>
    public class VoiceSession : MonoBehaviour
    {
        public const int InRate = 16000, OutRate = 24000, Frame = 512;

        public VoiceState State { get; private set; } = VoiceState.Off;
        public float MicLevel { get; private set; }          // 0..1, RMS of the last mic block (for the meter)
        public bool HandsFree { get; private set; }
        public const string HandsFreePref = "rapport.hands_free";  // the learner's last choice; push-to-talk until they pick hands-free
        public bool UseMicrophone = true;                     // false: only InjectMicAudio feeds the mic path (demo, tests)
        public bool Connected => ws != null && ws.State == WebSocketState.Open;

        public event Action<JObject> Event;                   // every JSON event from the service
        public event Action<int, string> SentenceStarted;     // (index, text) when that sentence actually starts playing
        public event Action Stopped;                          // the patient was cut off (barge-in or stop)

        ClientWebSocket ws;
        CancellationTokenSource cts;
        readonly ConcurrentQueue<object> inbox = new();      // string (JSON) or byte[] (PCM)
        readonly SemaphoreSlim sendLock = new(1, 1);

        // playback ring: written on the main thread, read on the audio thread
        readonly object ringLock = new();
        float[] ring = new float[OutRate * 120];
        long written, read;
        readonly Queue<(long start, int index, string text)> sentenceMarks = new();
        readonly Queue<(int index, string text, int samples)> pendingSentences = new();
        AudioSource output;

        // microphone
        string micDevice;
        AudioClip micClip;
        int micPos;
        readonly List<float> micBuf = new();
        readonly Queue<float> injected = new();

        public void Setup(AudioSource patientOutput)
        {
            output = patientOutput;
            var clip = AudioClip.Create("patient_stream", OutRate * 4, 1, OutRate, true, OnRead);
            output.clip = clip;
            output.loop = true;
            output.Play();
        }

        public async Task Connect(string baseUrl, JObject start)
        {
            var uri = new Uri(baseUrl.Replace("http://", "ws://").Replace("https://", "wss://").TrimEnd('/') + "/session");
            cts = new CancellationTokenSource();
            ws = new ClientWebSocket();
            await ws.ConnectAsync(uri, cts.Token);
            _ = Task.Run(ReceiveLoop);
            start["type"] = "start";
            HandsFree = start["hands_free"]?.Value<bool>() ?? false;
            await SendJson(start);
            if (UseMicrophone) StartMic();
        }

        void StartMic()
        {
            if (Microphone.devices.Length == 0) { Debug.LogWarning("PsychSim: no microphone found; typed input only"); return; }
            micDevice = Microphone.devices[0];
            micClip = Microphone.Start(micDevice, true, 2, InRate);
            micPos = 0;
        }

        public Task SendJson(JObject o) => Send(Encoding.UTF8.GetBytes(o.ToString(Newtonsoft.Json.Formatting.None)), WebSocketMessageType.Text);

        public Task SendText(string text) => SendJson(new JObject { ["type"] = "text", ["text"] = text });
        public Task SendState(Dictionary<string, float> state) => SendJson(new JObject { ["type"] = "state", ["state"] = JObject.FromObject(state) });

        public void SetHandsFree(bool on)
        {
            HandsFree = on;
            _ = SendJson(new JObject { ["type"] = "hands_free", ["on"] = on });
        }

        public void PushToTalk(bool down) => _ = SendJson(new JObject { ["type"] = down ? "ptt_begin" : "ptt_end" });

        /// <summary>Feeds 16 kHz mono samples into the same path as the microphone (sent in real time, 32 ms frames).</summary>
        public void InjectMicAudio(float[] samples16k) { lock (injected) foreach (var s in samples16k) injected.Enqueue(s); }
        public bool InjectedPending { get { lock (injected) return injected.Count > 0; } }

        async Task Send(byte[] data, WebSocketMessageType type)
        {
            if (!Connected) return;
            // ConfigureAwait(false): resuming on the main thread costs a frame per await, which capped the mic at ~30 frames/s
            // (it needs 31.25) and built a backlog that grew all session
            await sendLock.WaitAsync().ConfigureAwait(false);
            try { await ws.SendAsync(new ArraySegment<byte>(data), type, true, cts.Token).ConfigureAwait(false); }
            catch (Exception e) when (e is WebSocketException or OperationCanceledException or ObjectDisposedException) { }
            finally { sendLock.Release(); }
        }

        async Task ReceiveLoop()
        {
            var buf = new byte[1 << 16];
            var msg = new List<byte>();
            try
            {
                while (Connected)
                {
                    var r = await ws.ReceiveAsync(new ArraySegment<byte>(buf), cts.Token);
                    if (r.MessageType == WebSocketMessageType.Close) break;
                    msg.AddRange(new ArraySegment<byte>(buf, 0, r.Count));
                    if (!r.EndOfMessage) continue;
                    inbox.Enqueue(r.MessageType == WebSocketMessageType.Text ? Encoding.UTF8.GetString(msg.ToArray()) : msg.ToArray());
                    msg.Clear();
                }
            }
            catch (Exception e) when (e is WebSocketException or OperationCanceledException or ObjectDisposedException) { }
            inbox.Enqueue("{\"type\":\"closed\"}");
        }

        void Update()
        {
            while (inbox.TryDequeue(out var m))
            {
                if (m is byte[] pcm) OnPcm(pcm);
                else OnJson(JObject.Parse((string)m));
            }
            lock (ringLock)
                while (sentenceMarks.Count > 0 && sentenceMarks.Peek().start <= read)
                {
                    var s = sentenceMarks.Dequeue();
                    SentenceStarted?.Invoke(s.index, s.text);
                }
            if (State == VoiceState.Speaking && Buffered() == 0 && pendingSentences.Count == 0 && replyDone) SetState(VoiceState.Listening);
            PumpMic();
        }

        bool replyDone;

        void OnJson(JObject o)
        {
            switch ((string)o["type"])
            {
                case "listening": if (State != VoiceState.Speaking || Buffered() == 0) SetState(VoiceState.Listening); replyDone = true; break;
                case "vad_start": if (State != VoiceState.Speaking) SetState(VoiceState.Hearing); break;
                case "thinking": SetState(VoiceState.Thinking); replyDone = false; break;
                case "speaking": SetState(VoiceState.Speaking); break;
                case "sentence": pendingSentences.Enqueue(((int)o["index"], (string)o["text"], (int)o["samples"])); break;
                case "stop":
                    lock (ringLock) { read = written; sentenceMarks.Clear(); }
                    pendingSentences.Clear();
                    Stopped?.Invoke();
                    break;
                case "closed": SetState(VoiceState.Off); break;
            }
            Event?.Invoke(o);
        }

        void SetState(VoiceState s) => State = s;

        void OnPcm(byte[] b)
        {
            var (index, text, _) = pendingSentences.Count > 0 ? pendingSentences.Dequeue() : (-1, null, 0);
            int n = b.Length / 2;
            lock (ringLock)
            {
                if (written - read + n > ring.Length) Array.Resize(ref ring, ring.Length * 2);  // shortcut: grow only; a 2-min reply never happens
                if (text != null) sentenceMarks.Enqueue((written, index, text));
                for (int i = 0; i < n; i++) ring[(written + i) % ring.Length] = BitConverter.ToInt16(b, i * 2) / 32768f;
                written += n;
            }
            SetState(VoiceState.Speaking);
        }

        long Buffered() { lock (ringLock) return written - read; }

        // audio thread
        void OnRead(float[] data)
        {
            lock (ringLock)
            {
                for (int i = 0; i < data.Length; i++)
                    data[i] = read < written ? ring[read++ % ring.Length] : 0f;
            }
        }

        void PumpMic()
        {
            if (!Connected) return;
            if (micClip != null && UseMicrophone)
            {
                int pos = Microphone.GetPosition(micDevice);
                int count = (pos - micPos + micClip.samples) % micClip.samples;
                if (count > 0)
                {
                    var tmp = new float[count];
                    micClip.GetData(tmp, micPos);
                    micPos = pos;
                    micBuf.AddRange(tmp);
                }
            }
            else
            {
                // virtual mic: real-time pacing; injected speech when queued, otherwise silence like an open mic
                // while the Recorder captures, the clip being played advances by captureDeltaTime per frame; pacing by wall time
                // fell ~5% behind it and the backlog grew every turn
                micClock += Time.captureDeltaTime > 0f ? Time.captureDeltaTime : Time.unscaledDeltaTime;
                int due = (int)(micClock * InRate);
                micClock -= due / (float)InRate;
                lock (injected)
                    for (int i = 0; i < due; i++) micBuf.Add(injected.Count > 0 ? injected.Dequeue() : 0f);
            }
            while (micBuf.Count >= Frame)
            {
                var bytes = new byte[Frame * 2];
                float sum = 0;
                for (int i = 0; i < Frame; i++)
                {
                    float s = Mathf.Clamp(micBuf[i], -1f, 1f);
                    sum += s * s;
                    short v = (short)(s * 32767);
                    bytes[i * 2] = (byte)v; bytes[i * 2 + 1] = (byte)(v >> 8);
                }
                micBuf.RemoveRange(0, Frame);
                MicLevel = Mathf.Clamp01(Mathf.Sqrt(sum / Frame) * 6f);
                _ = Send(bytes, WebSocketMessageType.Binary);
            }
        }

        float micClock;

        async void OnDestroy()
        {
            if (micDevice != null) Microphone.End(micDevice);
            if (ws == null) return;
            try { if (Connected) await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "bye", CancellationToken.None); }
            catch (Exception) { }
            cts?.Cancel();
            ws.Dispose();
        }

        /// <summary>Linear resample (e.g. 24 kHz TTS to the 16 kHz mic path).</summary>
        public static float[] Resample(float[] src, int from, int to)
        {
            if (from == to) return src;
            var dst = new float[(int)((long)src.Length * to / from)];
            for (int i = 0; i < dst.Length; i++)
            {
                double x = (double)i * from / to;
                int a = (int)x; float f = (float)(x - a);
                dst[i] = a + 1 < src.Length ? src[a] * (1 - f) + src[a + 1] * f : src[Math.Min(a, src.Length - 1)];
            }
            return dst;
        }
    }
}
