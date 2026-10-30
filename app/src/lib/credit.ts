// A credit that says the photo was blurred already states how Lusot changed it (C617's CC BY change note), so the result
// card and the sample list leave out their own line about it. With no such credit they keep it.
export const creditStatesChange = (credit: string | undefined): boolean =>
  credit !== undefined && /\bblurred\b/i.test(credit)
