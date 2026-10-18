using UnityEngine;

namespace PsychSim.Speech
{
    [CreateAssetMenu(menuName = "PsychSim/Service Settings")]
    public class ServiceSettings : ScriptableObject
    {
        [Tooltip("Patient service. Localhost on Mac; a LAN address for Quest 3S (Stage 5).")]
        public string baseUrl = "http://127.0.0.1:8765";
        [Tooltip("Empty = the service default (grok-4.20-0309-non-reasoning).")]
        public string model = "";
        public int replyTimeoutS = 25;
        public int ttsTimeoutS = 15;
        [Tooltip("Doctor voice for the demo hook (male KittenTTS voice).")]
        public string doctorVoice = "Jasper";
    }
}
