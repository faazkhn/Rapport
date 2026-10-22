using System;
using System.Diagnostics;
using System.Text;
using System.Threading.Tasks;
using Newtonsoft.Json.Linq;
using Rapport.Patient;
using UnityEngine;
using UnityEngine.Networking;

namespace Rapport.Speech
{
    /// <summary>Text to speech. PatientServiceClient implements it over /tts; tests use a silent fake.</summary>
    public interface IVoice
    {
        Task<AudioClip> Speak(string text, string voice, float speed);
    }

    /// <summary>HTTP client for the local patient service (/reply, /tts). The API key never lives here; the service holds it.</summary>
    public class PatientServiceClient : IPatientService, IVoice
    {
        readonly ServiceSettings settings;
        public long LastTtsMs { get; private set; }

        public PatientServiceClient(ServiceSettings settings) { this.settings = settings; }

        public async Task<string> Reply(string requestJson)
        {
            using var req = Post("/reply", requestJson, settings.replyTimeoutS);
            await req.SendWebRequest();
            if (req.result != UnityWebRequest.Result.Success) throw new Exception($"/reply {req.responseCode} {req.error}");
            return req.downloadHandler.text;
        }

        /// <summary>GET /patient: the seeded patient the doctor will meet (slot values, style, start state), for the prebrief.</summary>
        public async Task<JObject> Patient(string caseId, string variant, int seed, string mode)
        {
            var url = $"{settings.baseUrl.TrimEnd('/')}/patient?case_id={UnityWebRequest.EscapeURL(caseId)}&variant={variant}&seed={seed}&mode={mode}";
            using var req = UnityWebRequest.Get(url);
            req.timeout = settings.replyTimeoutS;
            await req.SendWebRequest();
            if (req.result != UnityWebRequest.Result.Success) throw new Exception($"/patient {req.responseCode} {req.error}");
            return JObject.Parse(req.downloadHandler.text);
        }

        public async Task<AudioClip> Speak(string text, string voice, float speed)
        {
            var sw = Stopwatch.StartNew();
            var body = new JObject { ["text"] = text.Length > 1000 ? text.Substring(0, 1000) : text, ["voice"] = voice, ["speed"] = Mathf.Clamp(speed, 0.5f, 2f) };
            using var req = Post("/tts", body.ToString(), settings.ttsTimeoutS);
            await req.SendWebRequest();
            LastTtsMs = sw.ElapsedMilliseconds;
            if (req.result != UnityWebRequest.Result.Success) throw new Exception($"/tts {req.responseCode} {req.error}");
            return Wav.ToClip(req.downloadHandler.data, "tts");
        }

        UnityWebRequest Post(string path, string json, int timeoutS)
        {
            var req = new UnityWebRequest(settings.baseUrl.TrimEnd('/') + path, "POST")
            {
                uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(json)),
                downloadHandler = new DownloadHandlerBuffer(),
                timeout = timeoutS,
            };
            req.SetRequestHeader("Content-Type", "application/json");
            return req;
        }
    }

    /// <summary>16-bit PCM WAV (what /tts returns) to an AudioClip, in memory.</summary>
    public static class Wav
    {
        public static AudioClip ToClip(byte[] b, string name)
        {
            if (b.Length < 44 || Encoding.ASCII.GetString(b, 0, 4) != "RIFF") throw new FormatException("not a WAV file");
            int channels = BitConverter.ToInt16(b, 22), rate = BitConverter.ToInt32(b, 24), bits = BitConverter.ToInt16(b, 34);
            if (bits != 16) throw new FormatException($"expected 16-bit PCM, got {bits}");
            int pos = 12;
            while (pos + 8 <= b.Length && Encoding.ASCII.GetString(b, pos, 4) != "data") pos += 8 + BitConverter.ToInt32(b, pos + 4);
            int len = Math.Min(BitConverter.ToInt32(b, pos + 4), b.Length - pos - 8) / 2;
            var samples = new float[len];
            for (int i = 0; i < len; i++) samples[i] = BitConverter.ToInt16(b, pos + 8 + i * 2) / 32768f;
            var clip = AudioClip.Create(name, len / channels, channels, rate, false);
            clip.SetData(samples, 0);
            return clip;
        }
    }
}
