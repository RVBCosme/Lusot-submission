// One class per depth step, written out in full because Tailwind finds a class by reading the source. The ramp is one hue
// that grows stronger with depth (C624), so a level's fill is its own step. The gauge draws every step; the level chip on a
// sample draws the one step of its level.
export const FILL = [
  'bg-depth-1',
  'bg-depth-2',
  'bg-depth-3',
  'bg-depth-4',
  'bg-depth-5',
  'bg-depth-6',
  'bg-depth-7',
  'bg-depth-8',
  'bg-depth-9',
] as const

// A step that the water may reach, deeper than a floor: the same hue, faint. A faint fill, not a gradient: the design
// system has no gradients, and the dashed edge says "possible" as the fill alone could not.
export const FAINT = [
  'bg-depth-1/40',
  'bg-depth-2/40',
  'bg-depth-3/40',
  'bg-depth-4/40',
  'bg-depth-5/40',
  'bg-depth-6/40',
  'bg-depth-7/40',
  'bg-depth-8/40',
  'bg-depth-9/40',
] as const
