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

Only adults, 18 or older. Before your first upload, Lusot asks you to confirm your age and to accept a short consent notice. It asks the same before your first question to Ask Lusot. The app asks for the 18+ check before samples too, as before an upload, and enforces it.

### What Lusot collects

| What | When | Why |
|---|---|---|
| A photo you take in the app [or a 5-second clip, if clip mode ships] | when you report | to estimate the depth at that spot |
| Your phone's location (GPS), how accurate it is, and how far you moved the pin | with each report | to put the pin at the spot |
| The time the photo was taken, and the time it reached Lusot | with each report | to show how recent a reading is, and to turn away old photos |
| A random device id, made when you first open Lusot, on your phone or in your browser | with each report, question or flag | to limit how many reports and questions one device sends in an hour, and to count one flag per device on a pin |
| Your typed question, and your phone's location for a question about "dito" | when you ask | to answer from nearby reports |
| A flag you put on a wrong or fake pin | when you flag | to check or hide that pin |
| Your IP address, which comes with every upload | with each report | kept only in a failed upload's queue record, so the failure can be checked (up to 7 days) |

Lusot has no accounts. It never asks for your name, email or phone number.

### What happens to your photo

1. **Faces are blurred automatically before Meta receives the photo.** On Lusot's own server, a face detector that isn't Meta's blurs the faces it finds. Automatic blurring can miss some faces: very small, side-on, partly covered or in the dark. A face it misses reaches Meta unblurred.
2. **Meta analyses the face-blurred photo.** Lusot sends it to Meta's AI service, which outlines the water, wheels and people and names where the water reaches. Licence plates are not blurred before Meta receives the photo, only before Lusot stores it. So Meta receives them, along with everything else in the photo, such as bodies, clothes, houses and signs.
3. **Meta may use what it receives to improve its products.** While Meta's hackathon credits pay for Lusot's calls, Meta's billing page says content sent under those credits may be used for product improvement. When the credits run out, analysis pauses, and the app says "New analyses are paused right now. The map and the Tested page still work." Nothing is billed beyond the credits. Lusot uses photos only to estimate depth at one spot and show that result.
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
- **Demo pins and samples.** Lusot also shows labelled demo pins and sample photos. They come from people who agreed to share their photos for this, or from openly licensed photos (CC0, public domain or CC BY, never BY-SA, from Wikimedia Commons and Flickr). Each is credited on screen with its author, licence and a link to the file. Faces and plate numbers are blurred in all of them. An open-licensed demo pin shows the photo's own date, marked as an archive photo, and is always shown as a demo pin. They stay up longer than 3 hours and 7 days, and never count as reports.
- **Outside Metro Manila.** A photo taken outside Metro Manila is analysed, and the result is shown only to you. It never becomes a pin. The photo still goes to Meta as described above, and the report is kept for 7 days like any other.

### Ask Lusot

- **Typed questions** go to Meta's AI service, which answers them from the nearby reports Lusot finds: their level, place and time, which are public pins anyway. Lusot doesn't store your typed questions.
- **Questions** go to Meta on the same terms as photos: while the hackathon credits last, Meta may use them to improve its products. Meta may keep them with no fixed period. Lusot asks Meta not to store the requests that answer a question, and Meta accepts that.
- **Place names.** When your question names a place that isn't on Lusot's list of MMDA flood-prone spots, Lusot sends the place name, and nothing about you, to OpenStreetMap's Nominatim service to find it on the map. Lusot keeps OpenStreetMap's answers (a place's name and map position) for 7 days, or 1 day for a place it didn't find, filed under a one-way hash of the name, never the words you typed or who asked.
- **"Dito" questions.** A question about "dito" uses your phone's location to find reports near you. That location stays on Lusot's server: Meta receives only the distances to nearby reports, never your position, and Lusot doesn't store it.

### Who processes data, and where

| Who | What they do | Where |
|---|---|---|
| Amazon Web Services | Lusot's servers, storage, queue, logs and website | Singapore; the website is also served through AWS's worldwide network |
| Meta | AI analysis: outlining and reading photos, and answering questions | [Meta's locations] |
| OpenStreetMap Foundation | place-name lookups (Nominatim) and the map's images | [OpenStreetMap's locations] |
| Anthropic | an AI assistant (Claude) that Lusot's developer may use to check logs, flagged reports, privacy requests and the demo video | [Anthropic's locations] |

- **The map's images.** When you open the map, your phone loads the map's images from OpenStreetMap's servers, which see your IP address, as any website does. When you place a photo's pin, the map opens around your own position, so those servers also see which area is on your screen, within about 300 m of you (PRIV-Q5).
- **Your IP address.** When you upload a photo, the notice of your upload that reaches Lusot's queue carries your IP address. If the analysis fails, that notice is kept for up to 7 days so the failure can be checked, then deleted. Service logs keep no photos, locations or IP addresses.
- **The website.** The website is served from Amazon S3 through Amazon CloudFront with access logging off, so the website keeps no visitor's IP address. What the API does with IP addresses stays as described above, kept no longer than 7 days. This takes effect with the deploy that carries it (MS4 Task 15; PRIV-Q9).
- **An AI assistant.** Lusot's developer may use an AI assistant (Claude, by Anthropic) to check Lusot's logs, flagged reports, privacy requests and the demo video's frames, which can include a report's blurred photo and its pin, or what a privacy request says. Anthropic keeps what it receives for 30 days, or up to 2 years if its systems flag it for a usage-policy check (PRIV-Q10).

### How long Lusot keeps data

| Data | Kept for |
|---|---|
| your original photo | deleted after analysis; any leftover is removed, usually within two days |
| the blurred photo, its outlines, and the report (level, spot and times) | 7 days after the photo was taken, then removed in the background, usually within a few days |
| the notice of an upload whose analysis failed, with your IP address | up to 7 days |
| the random device id | Lusot's servers never store the id itself, only a one-way hash of it: in the hourly counters for 2 hours, and in a flag's record until 7 days after the flagged pin's photo was taken. Both are then removed in the background, usually within a few days (PRIV-Q7). |
| a pin on the map | fades after 1 hour; gone after 3 hours |
| service logs: timings, model names and the reasons for "can't tell" (never photos, locations or IP addresses) | 14 days |
| your typed questions | not stored |
| OpenStreetMap's answers for place names (a hashed name, the place's name and map position) | 7 days, or 1 day for a place not found |
| the website's access logs | none kept: access logging is off (PRIV-Q9) |

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

- *Taglish draft (M20):* Mga adult lang, 18 taong gulang pataas. Bago ang una mong upload, hinihiling ng Lusot na kumpirmahin mo ang edad mo at tanggapin ang maikling consent notice. Ganito rin bago ang una mong tanong sa Ask Lusot. Hinihingi rin ng app ang 18+ check bago ang mga sample, gaya bago ang upload, at ipinapatupad ito ng app.

### What Lusot collects

- *Taglish draft (M20):* Ang photo na kinunan mo sa app [o 5-second clip, kung isasama ang clip mode]. Kapag nag-report ka. Para tantyahin ang lalim sa spot na iyon.
- *Taglish draft (M20):* Ang lokasyon (GPS) ng phone mo, gaano ito katumpak, at gaano kalayo mo inilipat ang pin. Sa bawat report. Para mailagay ang pin sa spot.
- *Taglish draft (M20):* Ang oras na kinunan ang photo, at ang oras na dumating ito sa Lusot. Sa bawat report. Para makita kung gaano kabago ang reading, at para tanggihan ang lumang photo.
- *Taglish draft (M20):* Isang random na device id, ginagawa sa unang pagbukas mo ng Lusot, sa phone o sa browser. Sa bawat report, tanong o flag. Para limitahan kung ilang report at tanong ang maipapadala ng isang device kada oras, at para isang flag lang ang mabilang mula sa bawat device sa isang pin.
- *Taglish draft (M20):* Ang typed na tanong mo, at ang lokasyon ng phone mo para sa tanong tungkol sa "dito". Kapag nagtanong ka. Para sumagot mula sa mga kalapit na report.
- *Taglish draft (M20):* Ang flag na inilagay mo sa mali o pekeng pin. Kapag nag-flag ka. Para tingnan o itago ang pin na iyon.
- *Taglish draft (M20):* Ang IP address mo, na kasama ng bawat upload. Sa bawat report. Sine-save lang sa queue record ng upload na nabigo, para masuri ang problema (hanggang 7 araw).
- *Taglish draft (M20):* Walang account ang Lusot. Hindi nito kailanman hinihingi ang pangalan, email o phone number mo.

### What happens to your photo

1. *Taglish draft (M20):* **Awtomatikong bina-blur ang mga mukha bago matanggap ng Meta ang photo.** Sa sariling server ng Lusot, bina-blur ng isang face detector na hindi galing sa Meta ang mga mukhang nakikita nito. Puwedeng hindi ma-blur ng automatic blurring ang ilang mukha: napakaliit, nakatagilid, may takip, o nasa dilim. Ang mukhang hindi nito ma-blur ay matatanggap ng Meta nang hindi naka-blur.
2. *Taglish draft (M20):* **Sinusuri ng Meta ang photo na naka-blur ang mga mukha.** Ipinapadala ito ng Lusot sa AI service ng Meta, na nag-o-outline ng tubig, mga gulong at mga tao, at nagsasabi kung hanggang saan ang tubig. Hindi naka-blur ang plate number bago matanggap ng Meta ang photo, bago lang mag-store ang Lusot. Kaya matatanggap ito ng Meta, kasama ang lahat ng iba pang nasa photo, gaya ng katawan, damit, bahay at karatula.
3. *Taglish draft (M20):* **Puwedeng gamitin ng Meta ang natatanggap nito para pagandahin ang mga produkto nito.** Habang hackathon credits ng Meta ang nagbabayad sa mga tawag ng Lusot, sinasabi ng billing page ng Meta na puwedeng gamitin para sa product improvement ang content na ipinadala gamit ang credits na iyon. Kapag naubos na ang credits, napo-pause ang analysis, at sinasabi ng app: "Naka-pause ngayon ang mga bagong analysis. Gumagana pa rin ang mapa at ang Tested page." Walang sisingilin na lampas sa credits. Ginagamit lang ng Lusot ang mga photo para tantyahin ang lalim sa isang spot at ipakita ang resulta.
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
- *Taglish draft (M20):* **Demo pin at sample.** Nagpapakita rin ang Lusot ng mga demo pin at sample photo na may label. Galing ang mga ito sa mga taong pumayag na ibahagi ang photo nila para rito, o sa mga photo na bukas ang lisensya (CC0, public domain o CC BY, hindi kailanman BY-SA, mula sa Wikimedia Commons at Flickr). May credit sa screen ang bawat isa, kasama ang author, ang lisensya at link sa file. Naka-blur ang mga mukha at plate number sa lahat ng ito. Ang demo pin na galing sa photo na bukas ang lisensya ay nagpapakita ng sariling petsa ng photo, na may markang archive photo, at laging ipinapakita bilang demo pin. Mas matagal sila kaysa 3 oras at 7 araw, at hindi kailanman binibilang bilang report.
- *Taglish draft (M20):* **Sa labas ng Metro Manila.** Sinusuri ang photo na kinunan sa labas ng Metro Manila, at ikaw lang ang makakakita ng resulta. Hindi ito nagiging pin. Mapupunta pa rin ang photo sa Meta gaya ng nasa itaas, at sine-save ang report nang 7 araw, tulad ng iba.

### Ask Lusot

- *Taglish draft (M20):* **Ang typed na tanong** ay mapupunta sa AI service ng Meta, na sumasagot mula sa mga kalapit na report na nahanap ng Lusot: ang level, lugar at oras nila, na mga public pin naman. Hindi sine-save ng Lusot ang typed na tanong mo.
- *Taglish draft (M20):* **Ang mga tanong** ay napupunta sa Meta sa parehong terms ng mga photo: habang may hackathon credits pa, puwedeng gamitin ng Meta ang mga ito para pagandahin ang mga produkto nito. Puwedeng i-save ng Meta ang mga ito nang walang takdang tagal. Hinihiling ng Lusot sa Meta na huwag i-store ang mga request na sumasagot sa tanong, at pumapayag ang Meta.
- *Taglish draft (M20):* **Mga pangalan ng lugar.** Kapag may lugar sa tanong mo na wala sa listahan ng Lusot ng mga flood-prone spot ng MMDA, ipinapadala ng Lusot ang pangalan ng lugar, at walang anumang tungkol sa iyo, sa Nominatim service ng OpenStreetMap para mahanap ito sa mapa. Sine-save ng Lusot ang sagot ng OpenStreetMap (ang pangalan at posisyon ng lugar sa mapa) nang 7 araw, o 1 araw para sa lugar na hindi nito nahanap, sa ilalim ng one-way hash ng pangalan, hindi kailanman ang mga salitang tinype mo o kung sino ang nagtanong.
- *Taglish draft (M20):* **Mga tanong na "dito".** Ginagamit ng tanong tungkol sa "dito" ang lokasyon ng phone mo para maghanap ng report na malapit sa iyo. Nananatili ang lokasyong iyon sa server ng Lusot: ang layo lang sa mga kalapit na report ang natatanggap ng Meta, hindi kailanman ang posisyon mo, at hindi ito sine-save ng Lusot.

### Who processes data, and where

- *Taglish draft (M20):* Amazon Web Services: ang mga server, storage, queue, logs at website ng Lusot. Sa Singapore, at dumadaan din ang website sa worldwide network ng AWS.
- *Taglish draft (M20):* Meta: AI analysis, ibig sabihin ang pag-outline at pagbasa ng photo, at ang pagsagot sa tanong. [Mga lokasyon ng Meta.]
- *Taglish draft (M20):* OpenStreetMap Foundation: ang paghahanap ng pangalan ng lugar (Nominatim) at ang mga larawan ng mapa. [Mga lokasyon ng OpenStreetMap.]
- *Taglish draft (M20):* Anthropic: isang AI assistant (Claude) na puwedeng gamitin ng developer ng Lusot para suriin ang logs, ang mga na-flag na report, ang mga privacy request at ang demo video. [Mga lokasyon ng Anthropic.]
- *Taglish draft (M20):* **Ang mga larawan ng mapa.** Kapag binuksan mo ang mapa, kinukuha ng phone mo ang mga larawan ng mapa mula sa mga server ng OpenStreetMap, na nakakakita ng IP address mo, gaya ng anumang website. Kapag inilalagay mo ang pin ng photo mo, bumubukas ang mapa sa paligid ng posisyon mo, kaya nakikita rin ng mga server na iyon kung aling lugar ang nasa screen mo, mga 300 m mula sa iyo (PRIV-Q5).
- *Taglish draft (M20):* **Ang IP address mo.** Kapag nag-upload ka ng photo, may dalang IP address mo ang notice ng upload na dumarating sa queue ng Lusot. Kapag nabigo ang analysis, sine-save ang notice na iyon nang hanggang 7 araw para masuri ang problema, saka binubura. Walang photo, lokasyon o IP address sa service logs.
- *Taglish draft (M20):* **Ang website.** Inihahatid ang website mula sa Amazon S3 sa pamamagitan ng Amazon CloudFront na naka-off ang access logging, kaya walang IP address ng bisita ang sine-save ng website. Ang ginagawa ng API sa mga IP address ay nananatiling gaya ng nasa itaas, hanggang 7 araw lang. Magkakabisa ito sa deploy na may dala nito (MS4 Task 15; PRIV-Q9).
- *Taglish draft (M20):* **Isang AI assistant.** Puwedeng gumamit ang developer ng Lusot ng AI assistant (Claude, ng Anthropic) para suriin ang logs ng Lusot, ang mga na-flag na report, ang mga privacy request at ang mga frame ng demo video, na puwedeng may kasamang naka-blur na photo ng report at ang pin nito, o ang sinasabi ng privacy request. Itinatago ng Anthropic ang natatanggap nito nang 30 araw, o hanggang 2 taon kung ma-flag ito ng mga sistema nito para sa usage-policy check (PRIV-Q10).

### How long Lusot keeps data

- *Taglish draft (M20):* Ang orihinal mong photo: binubura pagkatapos ng analysis; anumang naiwan ay inaalis, kadalasan sa loob ng dalawang araw.
- *Taglish draft (M20):* Ang naka-blur na photo, ang mga outline nito, at ang report (level, spot at oras): 7 araw pagkatapos kunan ang photo, saka inaalis sa background, kadalasan sa loob ng ilang araw.
- *Taglish draft (M20):* Ang notice ng upload na nabigo ang analysis, kasama ang IP address mo: hanggang 7 araw.
- *Taglish draft (M20):* Ang random na device id: hindi kailanman sine-save ng servers ng Lusot ang id mismo, isang one-way hash lang nito: 2 oras sa hourly counters, at sa record ng isang flag hanggang 7 araw pagkatapos kunan ang photo ng pin na fini-flag. Pagkatapos, inaalis ang dalawa sa background, kadalasan sa loob ng ilang araw (PRIV-Q7).
- *Taglish draft (M20):* Ang pin sa mapa: lumalabo pagkalipas ng 1 oras, at nawawala pagkalipas ng 3 oras.
- *Taglish draft (M20):* Ang service logs (timing, pangalan ng model, at ang mga dahilan ng "can't tell"; hindi kailanman photo, lokasyon o IP address): 14 araw.
- *Taglish draft (M20):* Ang typed na tanong mo: hindi sine-save.
- *Taglish draft (M20):* Ang mga sagot ng OpenStreetMap para sa mga pangalan ng lugar (naka-hash na pangalan, pangalan at posisyon ng lugar sa mapa): 7 araw, o 1 araw para sa lugar na hindi nahanap.
- *Taglish draft (M20):* Ang access logs ng website: walang sine-save, naka-off ang access logging (PRIV-Q9).
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
  - **MS4's defaults** (spec draft 4, for Rene with these): "no flood seen" isn't a pin (MS4-Q2 (b), C506). A pin's detail shows the blurred photo and its overlay through 5-minute links, issued to anyone holding the pin's id while the pin is on the map (3 hours); an unpublished result's links are issued to the holder of its id for its 7 days (MS4-Q10 (a), C503). Past day 7 the report answers "not found" (C526). The page's brackets change to the chosen rule once Rene picks.
- **PRIV-Q3: Ask Lusot. Approved on its default (a)** by Claude under Rene's delegation (Oct 29, the tracker's check): no stored questions, `store: false` on Muse Spark, a place cache keyed by a hash (7 days, 1 day for a miss), a "dito" location that never leaves the server, and the 18+ check and notice before the first question. The page's brackets are filled to match (Ask Lusot's spec C720 and AskL-Q3). Ask Lusot is typed only since Oct 30 (7:28 AM), when its voice tasks were dropped: both drafts now describe typed questions only.
- **PRIV-Q4:** the contact for privacy requests. Held for Rene. No email address may be committed (CLAUDE.md; MS8's C903 scans the history), so the address reaches the page at build time from a git-ignored config, as the alarm email reaches the template from `samconfig.toml`, and never enters a committed file. Window 2 builds MS5's side.
- **PRIV-Q5:** whether to name OpenStreetMap's map servers. **Approved as drafted** (OpenStreetMap named), Oct 29. On Oct 30 (Window 2, MS5 Task 11, through the tracker at 1:51 PM), the line gained the place step: it loads the map's images around the person's own position, so OpenStreetMap also sees the area on screen, within about 300 m of them. The consent notice gained a line to match.
- **PRIV-Q6, settled by MS3a's C85 check** (run Oct 28, 8:37 to 8:40 PM; recorded in MS3a's C88). The "What Meta keeps" lines now state its result, and the brackets are gone.
  - SAM's streamed requests accept `store: false`, as the value the stream echoes shows, so every SAM request now sends it. Muse Spark's requests already send it, and Meta echoes it.
  - Meta's background mode, the fallback when SAM's service is slow, refuses `store: false`. That fallback keeps Meta's default, so the job is stored, and Lusot deletes it afterwards, as far as Meta allows.

  Meta's retention with no fixed period stays in the text. Rene approves the wording.
- **PRIV-Q7:** how long the device id and the hourly limit counters are kept. MS4's spec draft 4 (`e34a580`; its C508, C511 and C520) never stores the id itself, only its SHA-256 hash: for 2 hours in the counters (their TTL), and in a flag's record until the pin's `expiresAt`, 7 days after its photo was taken. DynamoDB's TTL then deletes both in the background, often days late, so the text says so, as the report's row does. Ask Lusot's question counters use the same table and TTL (its spec §4.8). The draft now says so, in English and Taglish, for Rene to approve (M21). **Approved on its default,** Oct 29.
- **PRIV-Q8:** the lawful basis for processing the data of people who appear in photos.
- **PRIV-Q9 with MS5-Q4: the website's hosting and its access logs. Decided: (c)** (one decision for both questions). The page states it as fact: the website is served from Amazon S3 through Amazon CloudFront with access logging off, so the website keeps no visitor's IP address, while the API's own handling of IP addresses stays as MS4 states it, kept no longer than 7 days. It takes effect with the deploy that carries it (MS4 Task 15). The Amplify GitHub connection (item 35) is moot.
  - The options were: (a) Amplify connected to GitHub; (b) Amplify in the SAM template, builds uploaded by script; (c) Amazon S3 and CloudFront in the template, access logging off, deployed by the same script.
  - Why (c): Amplify keeps access logs, with visitors' IP addresses, "until you delete the app", with no off switch (its user guide, checked through Context7), which breaks CLAUDE.md's "Keep data 7 days". (c) keeps no visitor IP address, inside AWS's free tier.
- **PRIV-Q10: Anthropic, through the developer's AI assistant.** Approved, policy only (Oct 29). Claude, the assistant Rene builds and runs Lusot with, can see app data while checking it: the service logs (timings, model names, reasons and report ids; never photos, locations, IP addresses or device ids, by design), a flagged report and its blurred photo when a pin is checked or hidden, privacy requests (MS9's C1013), the demo video's frames (MS8's C906), and Ask's test answers. The policy says so, with Anthropic's retention as Rene confirmed it (30 days with his model-improvement setting off; up to 2 years if flagged).
- **[clip mode]** and **[inches range]** stay only if clip mode ships and the release gate passes.
