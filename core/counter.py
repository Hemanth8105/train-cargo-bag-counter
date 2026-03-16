class BoxCounter:
    """
    Counts bags crossing a horizontal or vertical line.
    UP   = Loading   = IN
    DOWN = Unloading = OUT
    Total never goes below 0.
    Both IN and OUT count immediately on first crossing.
    """

    def __init__(self, line_position: float = 0.17, axis: str = "horizontal"):
        self.line_position  = line_position
        self.axis           = axis
        self.count          = 0
        self.count_in       = 0
        self.count_out      = 0
        self.counted_ids    = set()
        self._in_ids        = set()
        self._out_ids       = set()
        self.prev_pos       = {}
        self._cooldown      = {}

    def update(self, tracked_objects: dict, line_px: int):
        for obj_id, (x1, y1, x2, y2) in tracked_objects.items():
            pos = (x1 + x2) // 2 if self.axis == "vertical" else (y1 + y2) // 2

            if obj_id in self.counted_ids:
                self.prev_pos[obj_id] = pos
                continue

            if self._cooldown.get(obj_id, 0) > 0:
                self._cooldown[obj_id] -= 1
                self.prev_pos[obj_id] = pos
                continue

            if obj_id in self.prev_pos:
                prev = self.prev_pos[obj_id]

                crossed_fwd = prev < line_px <= pos    # DOWN = OUT
                crossed_bwd = prev > line_px >= pos    # UP   = IN

                if crossed_bwd:
                    # ── IN ────────────────────────────────────────────────────
                    self.count_in += 1
                    self.count    += 1
                    self._in_ids.add(obj_id)
                    self._out_ids.discard(obj_id)
                    self.counted_ids.add(obj_id)
                    self._cooldown[obj_id] = 20
                    print(f"[COUNT] Bag #{obj_id:>4}  IN  "
                          f"→  Total: {self.count}  "
                          f"(IN={self.count_in}  OUT={self.count_out})")

                elif crossed_fwd:
                    # ── OUT ───────────────────────────────────────────────────
                    self.count_out += 1
                    self._out_ids.add(obj_id)
                    self._in_ids.discard(obj_id)
                    self.counted_ids.add(obj_id)
                    self._cooldown[obj_id] = 20
                    if self.count > 0:
                        self.count -= 1
                    print(f"[COUNT] Bag #{obj_id:>4}  OUT "
                          f"→  Total: {self.count}  "
                          f"(IN={self.count_in}  OUT={self.count_out})")

            self.prev_pos[obj_id] = pos
