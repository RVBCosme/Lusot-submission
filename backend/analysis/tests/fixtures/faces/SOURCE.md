# Portrait test fixture

`portrait.jpg` is NASA's official portrait of astronaut Mae C. Jemison, resized for the face-blur tests.

| Field | Value |
|---|---|
| Title | "Official portrait of STS-47 Mission Specialist Mae C. Jemison in LES" |
| NASA ID | S92-40463, Johnson Space Center, July 1992 ([NASA Image and Video Library record](https://images.nasa.gov/details/S92-40463)) |
| Downloaded from | Wikimedia Commons, [File:Mae_Carol_Jemison.jpg](https://commons.wikimedia.org/wiki/File:Mae_Carol_Jemison.jpg), at `https://upload.wikimedia.org/wikipedia/commons/5/55/Mae_Carol_Jemison.jpg`: 6204 × 7755 px, 5,122,051 bytes, SHA-1 `7ba6b96b03f6e585953a3be15129924d1c486f00` (matches the SHA-1 Commons lists) |
| Licence | **Public domain.** Commons tags the file PD-USGov-NASA, with licence "Public domain" and no attribution required. NASA's [Images and Media Usage Guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/) say: "NASA content – images, audio, video, and media files used in the rendition of 3-dimensional models, such as texture maps and polygon data in any format – generally are not subject to copyright in the United States." |
| Changes | Resized to 640 × 800 px with OpenCV `INTER_AREA` and saved as JPEG quality 90. No metadata was kept. |
| SHA-256 of `portrait.jpg` | `fda68aba0601cda06057064a5da349129041d35240f16e627e2b2a5b177c6897` |
| Downloaded | Oct 28, 2026 |

**Use:** a unit-test fixture only. It never appears in the app, the demo or the video, and using it implies no endorsement by NASA. The same guidelines say: "NASA content used in a factual manner that does not imply endorsement may be used without needing explicit permission." and "NASA should be acknowledged as the source of the material."
