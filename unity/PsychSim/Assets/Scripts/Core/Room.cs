using UnityEngine;

namespace Rapport.Core
{
    /// <summary>
    /// Room contract: every room (placeholder or the artist's Room_* prefab) provides these named children; code finds them by name.
    /// PatientAnchor = patient root on the floor, 0.10 m in front of the seat edge, facing away from the backrest (seated clips put
    /// the hips 0.40 m behind it). ChairApproach = where walk_in ends and sit_down starts (same spot as PatientAnchor).
    /// </summary>
    public class Room
    {
        public Transform DoctorAnchor, PatientAnchor, Door, PatientSpawn, ChairApproach, CornerLookTarget, SoundSourceDoor, SoundSourceCorridor;

        public static Room Find()
        {
            return new Room
            {
                DoctorAnchor = Get("DoctorAnchor"), PatientAnchor = Get("PatientAnchor"), Door = Get("Door"), PatientSpawn = Get("PatientSpawn"),
                ChairApproach = Get("ChairApproach"), CornerLookTarget = Get("CornerLookTarget"),
                SoundSourceDoor = Get("SoundSource_Door"), SoundSourceCorridor = Get("SoundSource_Corridor"),
            };
        }

        static Transform Get(string name)
        {
            var go = GameObject.Find(name);
            if (go == null) throw new MissingReferenceException($"Room contract: no GameObject named '{name}' in the scene");
            return go.transform;
        }
    }
}
