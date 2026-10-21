using UnityEngine;

namespace Rapport.Speech
{
    [CreateAssetMenu(menuName = "PsychSim/Service Settings")]
    public class ServiceSettings : ScriptableObject
    {
        [Tooltip("Patient service. Localhost on Mac; a LAN address for Quest 3S (Stage 5).")]
        public string baseUrl = "http://127.0.0.1:8765";
        [Tooltip("Empty = the service default (the local llama-server model; Grok only when PATIENT_LLM=grok).")]
        public string model = "";
        [Tooltip("Silence (ms) that ends the doctor's turn in hands-free mode. Longer = fewer mid-sentence cuts, slower replies.")]
        public int vadSilenceMs = 500;
        public int replyTimeoutS = 25;
        public int ttsTimeoutS = 15;
        [Tooltip("Doctor voice for the demo hook (male KittenTTS voice).")]
        public string doctorVoice = "Hugo";
    }
}
