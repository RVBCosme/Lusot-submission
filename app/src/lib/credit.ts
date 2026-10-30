// A credit that says the photo was blurred already states how Lusot changed it (C617's CC BY change note), so the result
// card and the sample list leave out their own line about the blur. With no such credit they keep it.
export const creditStatesChange = (credit: string | undefined): boolean =>
  credit !== undefined && /\bblurred\b/i.test(credit)

// The same for the outlines a level result draws on the photo. MS4's sample credit states the blur only, since the photo
// it stores has none; its demo pin credit names them too.
export const creditStatesOutlines = (credit: string | undefined): boolean =>
  credit !== undefined && /\boutlines?\b/i.test(credit)
