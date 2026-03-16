import numpy as np

class BoxTracker:
    """
    Centroid-based multi-object tracker.
    Assigns a consistent integer ID to each bag across frames.

    Parameters
    ----------
    max_distance : int   – max pixel distance to still match a detection to a track
    max_missing  : int   – frames without a match before a track is dropped
    """

    def __init__(self, max_distance: int = 160, max_missing: int = 40):
        self.next_id      = 0
        self.tracked      = {}
        self.centroids    = {}
        self.missing      = {}
        self.max_distance = max_distance
        self.max_missing  = max_missing

    @staticmethod
    def _centroid(x1, y1, x2, y2):
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    def _register(self, det, centroid):
        self.tracked[self.next_id]   = det[:4]
        self.centroids[self.next_id] = centroid
        self.missing[self.next_id]   = 0
        self.next_id += 1

    def _drop(self, obj_id):
        self.tracked.pop(obj_id, None)
        self.centroids.pop(obj_id, None)
        self.missing.pop(obj_id, None)

    def update(self, detections: list) -> dict:
        """
        detections : list of (x1, y1, x2, y2, conf, cls)
        returns    : dict  {id: (x1, y1, x2, y2)}
        """
        if not detections:
            for obj_id in list(self.missing):
                self.missing[obj_id] += 1
                if self.missing[obj_id] > self.max_missing:
                    self._drop(obj_id)
            return self.tracked

        new_cents = [self._centroid(*d[:4]) for d in detections]

        if not self.centroids:
            for i, det in enumerate(detections):
                self._register(det, new_cents[i])
            return self.tracked

        old_ids   = list(self.centroids.keys())
        old_cents = [self.centroids[i] for i in old_ids]
        used_old  = set()
        used_new  = set()

        # Sort by distance — closest match first (better accuracy)
        pairs = []
        for ni, nc in enumerate(new_cents):
            for oi, oc in enumerate(old_cents):
                d = float(np.linalg.norm(np.array(nc) - np.array(oc)))
                pairs.append((d, ni, oi))
        pairs.sort(key=lambda x: x[0])

        for d, ni, oi in pairs:
            if ni in used_new or oi in used_old:
                continue
            if d > self.max_distance:
                break
            oid = old_ids[oi]
            self.tracked[oid]   = detections[ni][:4]
            self.centroids[oid] = new_cents[ni]
            self.missing[oid]   = 0
            used_old.add(oi)
            used_new.add(ni)

        # Register new detections
        for ni, det in enumerate(detections):
            if ni not in used_new:
                self._register(det, new_cents[ni])

        # Increment missing for unmatched tracks
        for oi, oid in enumerate(old_ids):
            if oi not in used_old:
                self.missing[oid] += 1
                if self.missing[oid] > self.max_missing:
                    self._drop(oid)

        return self.tracked
