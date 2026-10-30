// The level scale and the categories a result can carry. Each list is checked against backend rules.py and
// pipeline/types.py by levels.test.ts, so the app can't drift from what the pipeline writes (MS5 Task 4).

// The 9 ordered levels: MMDA's 7 gauge levels plus below_gutter and above_chest, which are outside its gauge.
export const LEVELS = [
  'below_gutter',
  'gutter',
  'half_knee',
  'half_tire',
  'knee',
  'tire',
  'waist',
  'chest',
  'above_chest',
] as const

export type Level = (typeof LEVELS)[number]

export type Passability = 'PATV' | 'NPLV' | 'NPATV'

// The class MMDA lists each level under. The two added levels carry the class of the gauge level they lie beyond.
export const PASSABILITY: Record<Level, Passability> = {
  below_gutter: 'PATV',
  gutter: 'PATV',
  half_knee: 'PATV',
  half_tire: 'NPLV',
  knee: 'NPLV',
  tire: 'NPATV',
  waist: 'NPATV',
  chest: 'NPATV',
  above_chest: 'NPATV',
}

// The two levels that aren't MMDA's: they never say "MMDA level" (CLAUDE.md, C81).
export const OFF_GAUGE: readonly Level[] = ['below_gutter', 'above_chest']

// The categories that can be a result's deciding landmark: Table 8's rows that read a level (rules.py).
export const WHEEL_LANDMARKS = ['tire_only', 'rim_quarter', 'hub', 'rim_three_quarters', 'rim_top', 'wheel_covered'] as const
export const PEOPLE_LANDMARKS = ['ankle', 'mid_shin', 'knee', 'mid_thigh', 'waist', 'chest', 'above_chest'] as const
// The body waterlines that read a level, always as a floor (C53).
export const BODY_FLOORS = ['mid_door', 'window'] as const

export type Landmark = (typeof WHEEL_LANDMARKS)[number] | (typeof PEOPLE_LANDMARKS)[number] | (typeof BODY_FLOORS)[number]

// The causes a numbered reference can carry in `dropped` (MS3b's evidence record: references.py, measure.py,
// waterline.py and geometry.py), which MS4 passes on in a reading and in the layers file (amendment 2). A reference with
// a cause has no level. levels.test.ts reads the causes those files write and checks this list against them both ways.
// A cause the app doesn't know reads as a general line.
export const DROP_CAUSES = [
  'vehicle_unanswered',
  'vehicle_moving',
  'vehicle_type',
  'vehicle_body_below_covered_wheel',
  'vehicle_wheels_disagree',
  'vehicle_no_reading',
  'wheel_vehicle_dropped',
  'wheel_unanswered',
  'wheel_methods_disagree',
  'person_unanswered',
  'person_not_adult',
  'person_wading',
  'person_no_reading',
  'no_water_contact',
  'ragged_waterline',
] as const

export type DropCause = (typeof DROP_CAUSES)[number]

// MS3a's refusalReason values (§3.4), which `status` tells apart (C50).
export const REFUSED_REASONS = [
  'too_dark',
  'too_blurry',
  'photo_unusable',
  'water_unsure',
  'no_water_found',
  'no_usable_reference',
  'references_disagree',
  'model_declined',
] as const

// MS3a's failed reasons, and MS1's pipeline_not_built, which stays readable on old reports for 7 days.
export const FAILED_REASONS = [
  'model_calls_paused',
  'photo_missing',
  'bad_file',
  'model_error',
  'pipeline_error',
  'pipeline_not_built',
] as const

export type Reason = (typeof REFUSED_REASONS)[number] | (typeof FAILED_REASONS)[number]
