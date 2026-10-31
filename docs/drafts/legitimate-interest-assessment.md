# Legitimate-interest assessment: people who appear in photos (draft)

This is a draft for Rene, the record behind PRIV-Q8's answer, (f), decided Oct 31. It is a builder's reading of the law, not legal advice. The National Privacy Commission's Guidelines on Legitimate Interest (NPC Circular 2023-07) ask a controller that relies on Section 12(f) of the Data Privacy Act (RA 10173) to put three tests in writing. They prescribe no form, and the Commission may ask to see the record.

- **Whose data:** people who happen to be in a photo someone sends Lusot: passers-by, people in vehicles, and the owners of vehicles whose plates show.
- **Which data:** their image in the photo (faces and bodies), and plates. Lusot never has their names. It has the photo's spot and time only because the sender shares them.
- **Why not consent:** they aren't Lusot's users, and Lusot never knows who they are, so they can't be asked. The sender's consent covers only the sender (the consent notice).

## 1. Purpose

**The purpose:** to show how deep floodwater is at one spot, in MMDA's levels, so that people can decide for themselves.

- **Why it's legitimate:** flood depth at street level is public-interest information, and it's lawful to collect and share. Lusot gives no crossing advice and describes no road or route, only the spot.

## 2. Necessity

- **The photo is needed:** it's the only evidence Lusot reads depth from. The depth is read against what stands in the water, such as a standing adult or a wheel; the model gives categories, and code does the measuring. So a person in the water can be the reference itself, and counts fully (D13).
- **The people are incidental:** Lusot doesn't look for them, and needs nothing about who they are. A face or plate adds nothing to the depth reading.
- **Less would not work:** a text-only report can't be checked. The photo with its outlines is what lets anyone check the reading.

## 3. Balancing

These protections are built in, and checkable in the code and the tests:

- **Before Meta:** a non-Meta face detector blurs faces before any photo goes to Meta (D12, C20). This is the pipeline's first step, for every photo, live or sample.
- **Before storage:** faces and plates are blurred again, from SAM's masks, before Lusot keeps a copy.
- **The original:** deleted after analysis. Any leftover is removed, usually within two days.
- **The blurred copy, its outlines and the report:** removed 7 days after the photo was taken.
- **On the map:** a pin fades after 1 hour and is gone after 3. Its blurred photo opens only while the pin is on the map, through 5-minute links. A photo taken outside Metro Manila is never pinned.
- **No identification:** no face recognition, no accounts, no names. Device ids are stored only as one-way hashes.
- **Logs:** they never hold a photo, a location or an IP address.
- **The person's rights:** anyone in a photo can object or ask for its deletion under the Act, and the policy says so.

**The weak spot, said openly:** plates are **not** blurred before the photo goes to Meta (D12, C20). Meta's Billing page says credit-paid content "may be used for product improvement", and the policy and consent notice say so plainly.

- **Why the balance still holds:** a plate identifies a vehicle, not a person. Linking it to a person takes government records that Meta doesn't hold.
- **What else limits it:** faces, the most identifying part, are blurred before Meta. Every request sends `store: false` where Meta accepts it, which is all but the background-mode fallback (PRIV-Q6).

**What's left:** automatic blurring can miss some faces and plates, and the policy says so too. Deletion, the 3-hour pin and the right to ask for removal limit the harm when it does.

**Conclusion:** the purpose is legitimate, the processing is necessary for it, and the people's rights don't override it, given these protections.

## Why Section 13 doesn't apply

Section 13's stricter rules govern sensitive personal information as Section 3(l) defines it: race, ethnic origin, age, health and similar details. Lusot detects faces only to blur them. It never identifies anyone, and never reads, infers or records anything about a person.

## When to look again

Review this before release (M21), and again if any of these change:
- the blurring
- what reaches Meta, or Meta's terms
- how long data is kept
- what a pin shows

## Sources

- RA 10173, Sections 3(l), 4(d), 12 and 13, as LawPhil prints them: https://lawphil.net/statutes/repacts/ra2012/ra_10173_2012.html (privacy.gov.ph refused the fetch with a 403).
- NPC Circular 2023-07, as summarised by Baker McKenzie: https://insightplus.bakermckenzie.com/bm/data-technology/philippines-national-privacy-commission-issues-guidelines-on-the-processing-of-personal-information-based-on-legitimate-interest. The circular's own text hasn't been read, nor checked for later amendments.
