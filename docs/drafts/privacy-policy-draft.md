# Lusot privacy policy: draft for Rene

> **Draft, Oct 28, 2026 (Window 4).** Rene approves every line (M21), and reviews the copy as a native speaker (M20). Text in square brackets depends on a result or decision that is still open; each is listed under "Open items" at the end. This draft is information, not legal advice.
>
> **Languages:** the app's text is English by default, with a Taglish switch (Rene, Oct 28, relayed by the tracker). So this page has an English version and a Taglish version. Every Taglish line is a draft for Rene's M20 review.

---

## English

**Lusot privacy policy**

Last updated: [date of publication]

Lusot estimates the depth of a flood at one spot from a photo you take. This page explains what Lusot collects, why, how long it keeps it, and who else receives it.

Not affiliated with MMDA.

### Who runs Lusot

Lusot is a solo project by Rene Vincent Cosme, built for the Meta Global AI Developer Hackathon. He is the person accountable for how Lusot handles personal data. Contact: [privacy contact, added at publication (PRIV-Q4)].

### Who can use Lusot

Only adults, 18 or older. Before your first upload, Lusot asks you to confirm your age and to accept a short consent notice. [It asks the same before your first question to Ask Lusot (PRIV-Q3).]

### What Lusot collects

| What | When | Why |
|---|---|---|
| A photo you take in the app [or a 5-second clip, if clip mode ships] | when you report | to estimate the depth at that spot |
| Your phone's location (GPS), how accurate it is, and how far you moved the pin | with each report | to put the pin at the spot |
| The time the photo was taken, and the time it reached Lusot | with each report | to show how recent a reading is, and to turn away old photos |
| A random device id, made when you first open Lusot, on your phone or in your browser | with each report or question | to limit how many reports and questions one device sends in an hour |
| Your typed question, or up to 15 seconds of audio for a spoken one, and your phone's location for a question about "dito" | when you ask | to answer from nearby reports |
| A flag you put on a wrong or fake pin | when you flag | to check or hide that pin |
| Your IP address, which comes with every upload | with each report | kept only in a failed upload's queue record, so the failure can be checked (up to 7 days) |

Lusot has no accounts. It never asks for your name, email or phone number.

### What happens to your photo

1. **Faces are blurred automatically before Meta receives the photo.** On Lusot's own server, a face detector that isn't Meta's blurs the faces it finds. Automatic blurring can miss some faces: very small, side-on, partly covered or in the dark. A face it misses reaches Meta unblurred.
2. **Meta analyses the face-blurred photo.** Lusot sends it to Meta's AI service, which outlines the water, wheels and people and names where the water reaches. Licence plates are not blurred before Meta receives the photo, only before Lusot stores it. So Meta receives them, along with everything else in the photo, such as bodies, clothes, houses and signs.
3. **Meta may use what it receives to improve its products.** Lusot's calls to Meta are paid with Meta's hackathon credits, and Meta's billing page says content sent under those credits may be used for product improvement. Lusot uses photos only to estimate depth at one spot and show that result.
4. **Faces and plates are blurred before Lusot keeps a copy.** Until the analysis ends, your original waits in a private storage area that only Lusot's analysis and its administrator can open. Then faces are blurred again, and licence plates are blurred, using the outlines Meta returns, which can also miss some. Other details in the photo stay visible.
5. **The original is deleted.** Lusot deletes your original photo as soon as the result is saved. An automatic rule removes any original left behind, usually within two days, for example after a failed analysis.
6. **Only a blurred copy is kept,** and only when Lusot gives a level.

[If clip mode ships: faces in a clip are blurred first, as in a photo. The clip is uploaded to Meta's file storage with a 1-hour expiry, and deleted from it after analysis.]

[If Meta's service needs it (MS4): Lusot may send a face-blurred photo to Meta's file storage instead, with a 1-hour expiry, and delete it there after analysis.]

### What Meta keeps

- **Meta may keep what it receives with no fixed period,** under its own terms. Lusot's 7-day deletion covers only Lusot's own copies, and can't delete what Meta keeps.
- **Lusot asks Meta not to store the requests that analyse your photo,** and Meta accepts that. Meta may still keep what it receives, as above.
  - **One exception:** when Meta's outlining service is slow, Lusot sends that request again as a background job, which Meta stores. Lusot deletes the job afterwards, as far as Meta allows, so until then Meta holds that copy of your face-blurred photo.
- Lusot never uses Meta's "contributor" model, which lets Meta train on what it receives.

### Public pins

- **When a result becomes a pin.** A photo taken inside Metro Manila that Lusot reads a level from becomes a public pin, on the map and in Lusot's public pin feed. [Whether a "no flood seen" result also becomes a pin is still being decided (PRIV-Q2).]
- **What a pin shows:**
  - the spot: your phone's GPS position, or where you nudged the pin, with the GPS accuracy
  - the time the photo was taken
  - the level, the landmark it was read from, and its passability class (PATV, NPLV or NPATV)
  - how many reference objects the reading used
  - [an inches range, only if Lusot's measurement passes its own tests]
- **The photo on a pin.** [In the app, a pin also shows the blurred photo with the outlines Lusot used, so anyone can check how the reading was made (PRIV-Q2).]
- **How long a pin stays.** A pin fades after 1 hour and leaves the map after 3 hours. The report and its blurred photo are deleted 7 days after the photo was taken. The storage services remove them in the background, usually within a few days after that. [Whether a pin's photo can still be opened through its link until then is checked when the backend is built (PRIV-Q2).]
- **The pin feed** carries only what the map shows, never photos, outlines or device ids. Other flood maps may copy pins from the feed, and Lusot can't delete their copies.
- **Demo pins and samples.** Lusot also shows labelled demo pins and sample photos. They come from people who agreed to share their photos for this, or from openly licensed public photos (CC0 or CC BY, from Wikimedia Commons and Flickr), each credited on screen. Faces and plate numbers are blurred in all of them. They stay up longer than 3 hours and 7 days, and never count as reports.
- **Outside Metro Manila.** A photo taken outside Metro Manila is analysed, and the result is shown only to you. It never becomes a pin. The photo still goes to Meta as described above, and the report is kept for 7 days like any other.

### Ask Lusot

- **Typed questions** go to Meta's AI service, which answers them from the nearby reports Lusot finds: their level, place and time, which are public pins anyway. [Lusot doesn't store your typed questions (PRIV-Q3).]
- **Spoken questions** send up to 15 seconds of audio to Meta's transcription service, and the text is then answered the same way. Lusot doesn't keep the audio.
- **Both** are paid with the same credits. Meta may keep them with no fixed period, and may use them to improve its products. [Whether Lusot asks Meta not to store questions is decided when Ask Lusot is built (PRIV-Q3).]
- **Place names.** When your question names a place that isn't on Lusot's list of MMDA flood-prone spots, Lusot sends the place name, and nothing about you, to OpenStreetMap's Nominatim service to find it on the map. Lusot keeps a list of place names and their map positions [for … (PRIV-Q3)], but not who asked.
- **"Dito" questions.** A question about "dito" uses your phone's location to find reports near you. [It may also pass that location to Meta's AI service to look them up. It isn't stored (PRIV-Q3).]

### Who processes data, and where

| Who | What they do | Where |
|---|---|---|
| Amazon Web Services | Lusot's servers, storage, queue, logs and website | Singapore; the website is also served through AWS's worldwide network |
| Meta | AI analysis: outlining and reading photos, transcribing spoken questions, and answering questions | [Meta's locations] |
| OpenStreetMap Foundation | place-name lookups (Nominatim) and the map's images | [OpenStreetMap's locations] |

- **The map's images.** When you open the map, your phone loads the map's images from OpenStreetMap's servers, which see your IP address, as any website does (PRIV-Q5).
- **Your IP address.** When you upload a photo, the notice of your upload that reaches Lusot's queue carries your IP address. If the analysis fails, that notice is kept for up to 7 days so the failure can be checked, then deleted. Service logs keep no photos, locations or IP addresses.
- [The website is hosted on AWS Amplify, which keeps access logs, including visitors' IP addresses, until the site is deleted (PRIV-Q9).]

### How long Lusot keeps data

| Data | Kept for |
|---|---|
| your original photo | deleted after analysis; any leftover is removed, usually within two days |
| the blurred photo, its outlines, and the report (level, spot and times) | 7 days after the photo was taken, then removed in the background, usually within a few days |
| the notice of an upload whose analysis failed, with your IP address | up to 7 days |
| the random device id | [kept for … (PRIV-Q7)] |
| a pin on the map | fades after 1 hour; gone after 3 hours |
| service logs: timings, model names and the reasons for "can't tell" (never photos, locations or IP addresses) | 14 days |
| your typed questions | [not stored (PRIV-Q3)] |
| the audio of a spoken question | not kept |
| the list of place names and their map positions | [… (PRIV-Q3)] |
| [the website's access logs, with IP addresses] | [until the site is deleted (PRIV-Q9)] |

These limits cover only Lusot's own copies. What Meta keeps is set by Meta's terms.

### Why Lusot may use this data

[You agree to the consent notice before your first upload, and Lusot relies on that for your photos and questions. People who appear in a photo haven't agreed to anything: Lusot blurs their faces and plates before keeping a copy (automatic blurring can miss some), and deletes it after 7 days. The lawful basis for processing their data is still open (PRIV-Q8).]

### Your rights

Under the Data Privacy Act of 2012 (Republic Act No. 10173), you can ask to see, correct or delete data about you, and you can object to how it's used. You can also complain to the National Privacy Commission at privacy.gov.ph. Lusot has no accounts, so include the time and place you took the photo [and the report id, if the app showed you one], so that Lusot can find your report. Contact: [privacy contact (PRIV-Q4)].

### Keeping data secure

- Lusot's keys stay on its servers. The app never calls Meta directly.
- Each upload link works for 5 minutes, and for one report only.
- A report that isn't a pin can be fetched only by its random report id.

### Changes to this policy

If anything here changes, this page and its date change too.

Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.

---

## Taglish (draft for M20; not for use until Rene approves it)

Each line follows the English version above, in the same order. The headings, "Not affiliated with MMDA." and the last line of the page stay in English until Rene decides otherwise (M20).

**Lusot privacy policy**

- *Taglish draft (M20):* Huling update: [petsa ng paglathala]
- *Taglish draft (M20):* Tinatantya ng Lusot ang lalim ng baha sa isang spot mula sa photo na kinunan mo. Ipinapaliwanag ng page na ito kung ano ang kinokolekta ng Lusot, bakit, gaano katagal ito sine-save, at sino pa ang nakakatanggap nito.

Not affiliated with MMDA.

### Who runs Lusot

- *Taglish draft (M20):* Ang Lusot ay solo project ni Rene Vincent Cosme, ginawa para sa Meta Global AI Developer Hackathon. Siya ang may pananagutan sa paghawak ng Lusot sa personal data. Contact: [privacy contact (PRIV-Q4)].

### Who can use Lusot

- *Taglish draft (M20):* Mga adult lang, 18 taong gulang pataas. Bago ang una mong upload, hinihiling ng Lusot na kumpirmahin mo ang edad mo at tanggapin ang maikling consent notice. [Ganito rin bago ang una mong tanong sa Ask Lusot (PRIV-Q3).]

### What Lusot collects

- *Taglish draft (M20):* Ang photo na kinunan mo sa app [o 5-second clip, kung isasama ang clip mode]. Kapag nag-report ka. Para tantyahin ang lalim sa spot na iyon.
- *Taglish draft (M20):* Ang lokasyon (GPS) ng phone mo, gaano ito katumpak, at gaano kalayo mo inilipat ang pin. Sa bawat report. Para mailagay ang pin sa spot.
- *Taglish draft (M20):* Ang oras na kinunan ang photo, at ang oras na dumating ito sa Lusot. Sa bawat report. Para makita kung gaano kabago ang reading, at para tanggihan ang lumang photo.
- *Taglish draft (M20):* Isang random na device id, ginagawa sa unang pagbukas mo ng Lusot, sa phone o sa browser. Sa bawat report o tanong. Para limitahan kung ilang report at tanong ang maipapadala ng isang device kada oras.
- *Taglish draft (M20):* Ang typed na tanong mo, o hanggang 15 segundong audio para sa spoken na tanong, at ang lokasyon ng phone mo para sa tanong tungkol sa "dito". Kapag nagtanong ka. Para sumagot mula sa mga kalapit na report.
- *Taglish draft (M20):* Ang flag na inilagay mo sa mali o pekeng pin. Kapag nag-flag ka. Para tingnan o itago ang pin na iyon.
- *Taglish draft (M20):* Ang IP address mo, na kasama ng bawat upload. Sa bawat report. Sine-save lang sa queue record ng upload na nabigo, para masuri ang problema (hanggang 7 araw).
- *Taglish draft (M20):* Walang account ang Lusot. Hindi nito kailanman hinihingi ang pangalan, email o phone number mo.

### What happens to your photo

1. *Taglish draft (M20):* **Awtomatikong bina-blur ang mga mukha bago matanggap ng Meta ang photo.** Sa sariling server ng Lusot, bina-blur ng isang face detector na hindi galing sa Meta ang mga mukhang nakikita nito. Puwedeng hindi ma-blur ng automatic blurring ang ilang mukha: napakaliit, nakatagilid, may takip, o nasa dilim. Ang mukhang hindi nito ma-blur ay matatanggap ng Meta nang hindi naka-blur.
2. *Taglish draft (M20):* **Sinusuri ng Meta ang photo na naka-blur ang mga mukha.** Ipinapadala ito ng Lusot sa AI service ng Meta, na nag-o-outline ng tubig, mga gulong at mga tao, at nagsasabi kung hanggang saan ang tubig. Hindi naka-blur ang plate number bago matanggap ng Meta ang photo, bago lang mag-store ang Lusot. Kaya matatanggap ito ng Meta, kasama ang lahat ng iba pang nasa photo, gaya ng katawan, damit, bahay at karatula.
3. *Taglish draft (M20):* **Puwedeng gamitin ng Meta ang natatanggap nito para pagandahin ang mga produkto nito.** Binabayaran ang mga tawag ng Lusot sa Meta gamit ang hackathon credits ng Meta, at sinasabi ng billing page ng Meta na puwedeng gamitin para sa product improvement ang content na ipinadala gamit ang credits na iyon. Ginagamit lang ng Lusot ang mga photo para tantyahin ang lalim sa isang spot at ipakita ang resulta.
4. *Taglish draft (M20):* **Bina-blur ang mga mukha at plate number bago mag-save ng kopya ang Lusot.** Habang hindi pa tapos ang analysis, naghihintay ang orihinal mong photo sa isang pribadong storage na ang analysis ng Lusot at ang administrator nito lang ang makakabukas. Pagkatapos, bina-blur ulit ang mga mukha, at bina-blur ang mga plate number, gamit ang mga outline na ibinalik ng Meta, na puwede ring makaligtaan ang ilan. Nakikita pa rin ang ibang detalye sa photo.
5. *Taglish draft (M20):* **Binubura ang orihinal.** Binubura ng Lusot ang orihinal mong photo kapag na-save na ang resulta. May awtomatikong rule na nag-aalis ng anumang orihinal na naiwan, kadalasan sa loob ng dalawang araw, halimbawa pagkatapos ng isang bigong analysis.
6. *Taglish draft (M20):* **Naka-blur na kopya lang ang sine-save,** at kapag may nabasang level lang ang Lusot.

- *Taglish draft (M20):* [Kung isasama ang clip mode: bina-blur din muna ang mga mukha sa clip, gaya sa photo. Ina-upload ang clip sa file storage ng Meta na mag-e-expire sa loob ng 1 oras, at binubura roon pagkatapos ng analysis.]
- *Taglish draft (M20):* [Kung kailangan ito ng service ng Meta (MS4): puwedeng ipadala ng Lusot ang photo na naka-blur ang mga mukha sa file storage ng Meta, na mag-e-expire sa loob ng 1 oras, at burahin ito roon pagkatapos ng analysis.]

### What Meta keeps

- *Taglish draft (M20):* **Puwedeng i-save ng Meta ang natatanggap nito nang walang takdang tagal,** ayon sa sarili nitong terms. Sakop lang ng 7-day deletion ng Lusot ang sariling kopya ng Lusot, at hindi nito mabubura ang sine-save ng Meta.
- *Taglish draft (M20):* **Hinihiling ng Lusot sa Meta na huwag i-store ang mga request na sumusuri sa photo mo,** at pumapayag ang Meta. Puwede pa ring i-save ng Meta ang natatanggap nito, gaya ng nasa itaas.
  - *Taglish draft (M20):* **Isang exception:** kapag mabagal ang outlining service ng Meta, ipinapadala ulit ng Lusot ang request na iyon bilang background job, na sine-save ng Meta. Binubura ng Lusot ang job pagkatapos, hangga't pinapayagan ng Meta, kaya hanggang noon ay hawak ng Meta ang kopyang iyon ng photo mo na naka-blur ang mga mukha.
- *Taglish draft (M20):* Hindi kailanman ginagamit ng Lusot ang "contributor" model ng Meta, na nagpapahintulot sa Meta na mag-train gamit ang natatanggap nito.

### Public pins

- *Taglish draft (M20):* **Kailan nagiging pin ang resulta.** Ang photo na kinunan sa loob ng Metro Manila at may nabasang level ay nagiging public pin, sa mapa at sa public pin feed ng Lusot. [Pinagpapasyahan pa kung magiging pin din ang resultang "no flood seen" (PRIV-Q2).]
- *Taglish draft (M20):* **Ano ang ipinapakita ng pin:** ang spot, na GPS position ng phone mo o kung saan mo inilipat ang pin, kasama ang katumpakan ng GPS; ang oras na kinunan ang photo; ang level, ang landmark na pinagbasahan nito, at ang passability class nito (PATV, NPLV o NPATV); kung ilang reference object ang ginamit sa reading; [at inches range, kung pumasa lang ang sariling test ng Lusot].
- *Taglish draft (M20):* **Ang photo sa pin.** [Sa app, makikita rin sa pin ang naka-blur na photo kasama ang mga outline na ginamit ng Lusot, para masuri ng kahit sino kung paano nabasa ang lalim (PRIV-Q2).]
- *Taglish draft (M20):* **Gaano katagal ang pin.** Lumalabo ang pin pagkalipas ng 1 oras, at nawawala sa mapa pagkalipas ng 3 oras. Binubura ang report at ang naka-blur na photo nito 7 araw pagkatapos kunan ang photo. Inaalis ito ng mga storage service sa background, kadalasan sa loob ng ilang araw pagkatapos. [Titingnan kapag binuo na ang backend kung mabubuksan pa ang photo ng pin sa link nito hanggang noon (PRIV-Q2).]
- *Taglish draft (M20):* **Ang pin feed** ay may dala lang na nakikita sa mapa, hindi kailanman photo, outline o device id. Puwedeng kopyahin ng ibang flood map ang mga pin mula sa feed, at hindi mabubura ng Lusot ang kopya nila.
- *Taglish draft (M20):* **Demo pin at sample.** Nagpapakita rin ang Lusot ng mga demo pin at sample photo na may label. Galing ang mga ito sa mga taong pumayag na ibahagi ang photo nila para rito, o sa mga pampublikong photo na bukas ang lisensya (CC0 o CC BY, mula sa Wikimedia Commons at Flickr), na may credit sa screen ang bawat isa. Naka-blur ang mga mukha at plate number sa lahat ng ito. Mas matagal sila kaysa 3 oras at 7 araw, at hindi kailanman binibilang bilang report.
- *Taglish draft (M20):* **Sa labas ng Metro Manila.** Sinusuri ang photo na kinunan sa labas ng Metro Manila, at ikaw lang ang makakakita ng resulta. Hindi ito nagiging pin. Mapupunta pa rin ang photo sa Meta gaya ng nasa itaas, at sine-save ang report nang 7 araw, tulad ng iba.

### Ask Lusot

- *Taglish draft (M20):* **Ang typed na tanong** ay mapupunta sa AI service ng Meta, na sumasagot mula sa mga kalapit na report na nahanap ng Lusot: ang level, lugar at oras nila, na mga public pin naman. [Hindi sine-save ng Lusot ang typed na tanong mo (PRIV-Q3).]
- *Taglish draft (M20):* **Ang spoken na tanong** ay nagpapadala ng hanggang 15 segundong audio sa transcription service ng Meta, saka sinasagot ang text sa parehong paraan. Hindi sine-save ng Lusot ang audio.
- *Taglish draft (M20):* **Pareho silang** binabayaran ng parehong credits. Puwedeng i-save ng Meta ang mga ito nang walang takdang tagal, at puwedeng gamitin para pagandahin ang mga produkto nito. [Pagpapasyahan kapag binuo na ang Ask Lusot kung hihilingin ng Lusot sa Meta na huwag i-store ang mga tanong (PRIV-Q3).]
- *Taglish draft (M20):* **Mga pangalan ng lugar.** Kapag may lugar sa tanong mo na wala sa listahan ng Lusot ng mga flood-prone spot ng MMDA, ipinapadala ng Lusot ang pangalan ng lugar, at walang anumang tungkol sa iyo, sa Nominatim service ng OpenStreetMap para mahanap ito sa mapa. Nagse-save ang Lusot ng listahan ng mga pangalan ng lugar at ng posisyon nila sa mapa [nang … (PRIV-Q3)], pero hindi kung sino ang nagtanong.
- *Taglish draft (M20):* **Mga tanong na "dito".** Ginagamit ng tanong tungkol sa "dito" ang lokasyon ng phone mo para maghanap ng report na malapit sa iyo. [Puwede rin itong ipasa sa AI service ng Meta para hanapin ang mga report. Hindi ito sine-save (PRIV-Q3).]

### Who processes data, and where

- *Taglish draft (M20):* Amazon Web Services: ang mga server, storage, queue, logs at website ng Lusot. Sa Singapore, at dumadaan din ang website sa worldwide network ng AWS.
- *Taglish draft (M20):* Meta: AI analysis, ibig sabihin ang pag-outline at pagbasa ng photo, ang pag-transcribe ng spoken na tanong, at ang pagsagot sa tanong. [Mga lokasyon ng Meta.]
- *Taglish draft (M20):* OpenStreetMap Foundation: ang paghahanap ng pangalan ng lugar (Nominatim) at ang mga larawan ng mapa. [Mga lokasyon ng OpenStreetMap.]
- *Taglish draft (M20):* **Ang mga larawan ng mapa.** Kapag binuksan mo ang mapa, kinukuha ng phone mo ang mga larawan ng mapa mula sa mga server ng OpenStreetMap, na nakakakita ng IP address mo, gaya ng anumang website (PRIV-Q5).
- *Taglish draft (M20):* **Ang IP address mo.** Kapag nag-upload ka ng photo, may dalang IP address mo ang notice ng upload na dumarating sa queue ng Lusot. Kapag nabigo ang analysis, sine-save ang notice na iyon nang hanggang 7 araw para masuri ang problema, saka binubura. Walang photo, lokasyon o IP address sa service logs.
- *Taglish draft (M20):* [Naka-host ang website sa AWS Amplify, na nagse-save ng access logs, kasama ang IP address ng mga bisita, hanggang mabura ang site (PRIV-Q9).]

### How long Lusot keeps data

- *Taglish draft (M20):* Ang orihinal mong photo: binubura pagkatapos ng analysis; anumang naiwan ay inaalis, kadalasan sa loob ng dalawang araw.
- *Taglish draft (M20):* Ang naka-blur na photo, ang mga outline nito, at ang report (level, spot at oras): 7 araw pagkatapos kunan ang photo, saka inaalis sa background, kadalasan sa loob ng ilang araw.
- *Taglish draft (M20):* Ang notice ng upload na nabigo ang analysis, kasama ang IP address mo: hanggang 7 araw.
- *Taglish draft (M20):* Ang random na device id: [nang … (PRIV-Q7)].
- *Taglish draft (M20):* Ang pin sa mapa: lumalabo pagkalipas ng 1 oras, at nawawala pagkalipas ng 3 oras.
- *Taglish draft (M20):* Ang service logs (timing, pangalan ng model, at ang mga dahilan ng "can't tell"; hindi kailanman photo, lokasyon o IP address): 14 araw.
- *Taglish draft (M20):* Ang typed na tanong mo: [hindi sine-save (PRIV-Q3)].
- *Taglish draft (M20):* Ang audio ng spoken na tanong: hindi sine-save.
- *Taglish draft (M20):* Ang listahan ng mga pangalan ng lugar at ng posisyon nila sa mapa: [… (PRIV-Q3)].
- *Taglish draft (M20):* [Ang access logs ng website, kasama ang IP address: hanggang mabura ang site (PRIV-Q9).]
- *Taglish draft (M20):* Sakop lang ng mga limit na ito ang sariling kopya ng Lusot. Ang sine-save ng Meta ay nasa ilalim ng terms ng Meta.

### Why Lusot may use this data

- *Taglish draft (M20):* [Pumapayag ka sa consent notice bago ang una mong upload, at iyon ang batayan ng Lusot para sa mga photo at tanong mo. Hindi pumayag sa anuman ang mga taong nasa photo: bina-blur ng Lusot ang mga mukha at plate number nila bago mag-save ng kopya (puwedeng may hindi ma-blur ng automatic blurring), at binubura ito pagkalipas ng 7 araw. Bukas pa ang tanong kung ano ang lawful basis para sa data nila (PRIV-Q8).]

### Your rights

- *Taglish draft (M20):* Sa ilalim ng Data Privacy Act of 2012 (Republic Act No. 10173), puwede mong hilinging makita, itama o burahin ang data tungkol sa iyo, at puwede kang tumutol sa paggamit nito. Puwede ka ring magreklamo sa National Privacy Commission sa privacy.gov.ph. Walang account sa Lusot, kaya isama ang oras at lugar ng pagkuha mo ng photo [at ang report id, kung ipinakita ito ng app], para mahanap ng Lusot ang report mo. Contact: [privacy contact (PRIV-Q4)].

### Keeping data secure

- *Taglish draft (M20):* Nasa mga server lang ng Lusot ang mga key nito. Hindi kailanman direktang tumatawag sa Meta ang app.
- *Taglish draft (M20):* Gumagana ang bawat upload link nang 5 minuto, at para sa isang report lang.
- *Taglish draft (M20):* Ang report na hindi pin ay makukuha lang gamit ang random na report id nito.

### Changes to this policy

- *Taglish draft (M20):* Kapag may nagbago rito, magbabago rin ang page na ito at ang petsa nito.

Lusot estimates depth at one spot. It is not advice to cross. Follow MMDA and local advisories.

---

## Open items (for Rene; not part of the page)

The full questions, with options and defaults, are in Window 4's handoff note.

- **PRIV-Q1:** whether Lusot must register with the National Privacy Commission (the handoff note has the official sources).
- **PRIV-Q2: what a pin exposes.**
  - whether a "no flood seen" result becomes a pin (MS4)
  - whether a pin's detail shows the blurred photo with its outlines to everyone (the plan's overlay feature says anyone can check the reading)
  - whether a pin's photo link still opens until day 7
- **PRIV-Q3: Ask Lusot.**
  - Plan §13 says spoken questions are never stored, and the audio line is written that way. It says nothing about typed questions or a "dito" location; the plan's data model has no field for either.
  - whether a "dito" location reaches Meta, and whether questions are sent with `store: false`
  - how long the place-name list is kept
  - whether the age check and the notice come before the first question too. Plan Table 4 puts them only before the first upload, but questions go to Meta as well, and Meta's terms require adult users.
- **PRIV-Q4:** the contact for privacy requests. No email address may be written into the repo, so it is added when the page is published.
- **PRIV-Q5:** whether to name OpenStreetMap's map servers.
- **PRIV-Q6, settled by MS3a's C85 check** (run Oct 28, 8:37 to 8:40 PM; recorded in MS3a's C88). The "What Meta keeps" lines now state its result, and the brackets are gone.
  - SAM's streamed requests accept `store: false`, as the value the stream echoes shows, so every SAM request now sends it. Muse Spark's requests already send it, and Meta echoes it.
  - Meta's background mode, the fallback when SAM's service is slow, refuses `store: false`. That fallback keeps Meta's default, so the job is stored, and Lusot deletes it afterwards, as far as Meta allows.

  Meta's retention with no fixed period stays in the text. Rene approves the wording.
- **PRIV-Q7:** how long the device id and the hourly limit counters are kept (MS4).
- **PRIV-Q8:** the lawful basis for processing the data of people who appear in photos.
- **PRIV-Q9: the website's access logs** (raised by the tracker as its "PRIV-Q2"; numbered 9 here because Q2 was already taken). AWS Amplify Hosting keeps web access logs, which hold visitors' IP addresses, until the app is deleted, which may be indefinite.
  - (a) Keep Amplify, say so in the policy, and delete the app at the MS10 teardown, if there is one.
  - (b) Define the hosting in the template with access logging off. That is a plan change.
  - **Recommended: (a).**
- **[clip mode]** and **[inches range]** stay only if clip mode ships and the release gate passes.
