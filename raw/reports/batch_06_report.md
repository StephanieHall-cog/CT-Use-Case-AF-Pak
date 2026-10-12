# Generation Jihad — batch_06 report

**Pipeline:** faster-whisper `distil-large-v3` (CPU int8, 8 vCPU, ~4.7x realtime; no fallback to `small.en` needed). Total audio 560 min; transcription wall-clock ~97 min. All 10 episodes transcribed and extracted; no download or transcription failures.

**Extraction method (important for the merge):** the Anthropic account ran out of credits ("credit balance too low", account-wide) after three episodes. Episodes **6, 23, 35** were extracted with `extract.py` (Claude). Episodes **44, 141, 153, 194, 238, 321, 332** were extracted **manually** by the analyst from the transcripts into the same schema/paths (`manual/mNNN.py` generators are included for traceability). Manual extractions are deliberately conservative: every relationship carries a transcript timestamp and quote; inferences are marked `confidence: "inferred"`.

Script change: `extract.py` chunk size lowered 60k→35k→24k chars and `max_tokens` raised to 32000 because the shipped settings truncated dense episodes (ep 6 re-run went 31→57 relationships). Output shape unchanged.

| idx | Title | Date | Audio (min) | Transcribe (min) | Extraction |
|---|---|---|---|---|---|
| 6 | Ep. 5 – Banned in Pakistan | 2020-04-14 | 65.4 | 13.8 | Claude |
| 23 | Ep. 22 – Conspiracies Everywhere | 2020-08-18 | 54.0 | 11.7 | Claude |
| 35 | Ep. 34 – An Assassination in Tehran | 2020-12-02 | 52.7 | 11.3 | Claude |
| 44 | Ep. 43 – The Status of ISIS and Al Qaeda (guest Edmund Fitton-Brown, UN MT) | 2021-02-10 | 60.3 | 13.2 | manual |
| 141 | Ep. 140 – New UN report on al Qaeda and Islamic State | 2024-02-06 | 86.6 | 17.5 | manual |
| 153 | Ep. 152 – About that Afghanistan hearing yesterday | 2024-03-20 | 19.0 | 3.5 | manual |
| 194 | Ep. 198 – The state of global jihad with Preston Stewart | 2024-08-05 | 70.6 | 10.1 | manual |
| 238 | Status update on global jihad (UN MT report) | 2025-02-14 | 76.1 | 9.9 | manual |
| 321 | Dune: The Brotherhood Jihad | 2026-05-18 | 33.4 | 2.8 | manual |
| 332 | Seeking forgiveness from the Taliban | 2026-07-29 | 42.1 | 3.5 | manual |

Totals: 177 person entries (≈120 unique), 250 organizations, 207 places, 152 events, 359 relationships.

Quality-pass notes: timestamps normalized to `MM:SS`; duplicate persons/events in ep 35 merged (Mullah Omar); guests who are actors (Edmund Fitton-Brown, Preston Stewart, Will Selber) kept with `is_presenter_or_guest=true`; Bill Roggio kept as a person only in ep 6 where he is the subject (LWJ banned in Pakistan, Gen. Tariq Khan tour). Episodes 194 and 321 are mostly Middle East/Muslim Brotherhood content with only incidental AfPak material; extracted fully anyway. Ep 44 host misspoke al-Masri's death as "August 7, 1998" (it is 2020). Ep 141 host dated Wuhayshi's death to 2013 (actual 2015); recorded as stated with a note.

## Analyst summary — networks revealed in this batch

**Key individuals (role / affiliation / family)**
1. **Sirajuddin Haqqani** – Haqqani Network leader, Taliban deputy emir (2020), "warlord of the Taliban"; son of **Jalaluddin Haqqani** (CIA-backed 1980s commander, bin Laden benefactor, d. 2018). Haqqanis "incubated" al-Qaeda, are an integral part of the Taliban, were in talks with AQ about a new fighting force (2021), and were seen by the UN inside ISKP. Author of the NYT op-ed "What We, the Taliban, Want" used by Roggio in court to prove Haqqani = Taliban (ep 332).
2. **Hibatullah Akhundzada** – Taliban emir; his own son was a suicide bomber (ep 332).
3. **Ayman al-Zawahiri** – AQ emir; rumored dead Oct 2020, UN assumed alive (ep 44); killed by US in Kabul 2022; Taliban deny he was there, which blocks AQ from naming a successor (ep 141).
4. **Saif al-Adel** – Egyptian AQ veteran in Iran; next-in-line after al-Masri (ep 35/44); de facto AQ emir after 2022 (ep 141); by 2025 directing reorganization of AQ in Afghanistan, sleeper cells in Iraq/Syria/Libya/Europe, and drawing AQAP/Shabaab toward Iran's axis (ep 238). Son **Khalid (Muhammad Salah al-Din Zaidan)** ran AQ's liaison to AQAP in Yemen, protected by **Ibrahim al-Banna**, killed 22 Mar 2024.
5. **Abu Muhammad al-Masri (Abdullah Ahmed Abdullah)** – AQ deputy emir, killed by Israeli operatives at US behest in Tehran, 7 Aug 2020, with daughter **Miriam**, widow of **Hamza bin Laden** (married in Iran, "cementing the great houses of al-Qaeda"). Released from Iranian detention 2015 in an AQAP diplomat swap.
6. **Abd al-Rahman al-Maghrebi** – Moroccan AQ general manager, **son-in-law of Zawahiri**, in Iran per Pompeo (Jan 2021).
7. **Abdul Haq al-Turkistani** – TIP/ETIM emir, member of AQ's Shura, based in Kabul while commanding TIP forces inside HTS in Syria (ep 238).
8. **Noor Wali Mehsud** – TTP emir who reunified Jamaat-ul-Ahrar and the Mehsud faction with AQ mediation (ep 44); TTP ~6,000 fighters (2021), 600 attacks in H2 2024 under the joint "Tehrik-e-Jihad Pakistan" brand (ep 238).
9. **Asim Umar** – first AQIS emir, killed Sept 2019 in a Taliban stronghold in Helmand; Taliban negotiated his Pakistani wife's release from Afghan custody (ep 44).
10. **Omar Saeed Sheikh / Khalid Sheikh Mohammed** – Pearl kidnapping/murder; Pakistani court overturned Sheikh's conviction (2020) (ep 6).
11. **Hafiz Saeed, Sufi Muhammad → Maulana Fazlullah (father/son), Hakimullah Mehsud, Hafiz Gul Bahadur** – Pakistani jihadist ecosystem and TTP/TNSM succession (ep 6).
12. **Atiyah Abd al-Rahman** – bin Laden's chief of staff; role in reconstituting the TTP (ep 44).
13. **Abu Ikhlas al-Masri, Hamza al-Ghamdi** – AQ figures whose families are protected by the Taliban GDI (ep 238).
14. **Khalid Batarfi → Saad al-Awlaki** – AQAP succession (Batarfi arrested late 2020, later died; Awlaki, a tribal Yemeni, keeps comms with Saif al-Adel).
15. **Abdul Qadir Mumin / Abu Khadija al-Iraqi** – ISIS's two top figures (Somalia al-Karrar office vs GDP/Delegated Committee); **Sanaullah Ghafari** heads ISKP; **Bilal al-Sudani** (al-Karrar) funded ISKP ~$25k/month until killed by the US.
16. **Zalmay Khalilzad, Mark Milley, Kenneth McKenzie, Austin Scott Miller** – US actors in the Doha deal and withdrawal; **Badri 313** (Haqqani "jackboots") was the US partner unit at Kabul airport (ep 153).

**Key organizational relationships**
- Taliban ⇄ al-Qaeda: UN finds "little evidence of change" (2021); permissive environment, camps in 6→10→12+ of 34 provinces, Panjshir weapons depot, safe houses in Herat/Farah/Helmand/Kabul feeding a facilitation network into Iran, GDI protection for AQ families (2024-25).
- Haqqani Network ⊂ Taliban; Haqqani ⇄ al-Qaeda (incubator, joint force talks); Haqqani traces inside ISKP (UN 2021) — but hosts and UN insist Taliban–ISKP rivalry is real (ep 238).
- Taliban/AQIS ⇄ TTP against Pakistan; Taliban ⇄ Jamaat Ansarullah against Tajikistan; TIP and Uzbek groups (KTJ, KIB) straddle Afghanistan and HTS-run Syria.
- Iran ⇄ al-Qaeda: 9/11 Commission/Hezbollah training (1998), Obama-era Treasury designation of the "secret deal", al-Masri/Saif al-Adel/al-Maghrebi residency, AQ finances moving Iran→Kunar; Iran–Taliban talks on managing AQ risk (inferred).
- Pakistan: ISI–Haqqani/Taliban sponsorship (ep 6); by 2024-25 Pakistan is the Taliban's "ungrateful former friend" and target of TTP.
- Cross-sectarian truces: AQAP–Houthis (non-aggression, prisoners, weapons), Houthis–al-Shabaab (weapons for piracy), JNIM–ISGS.

**Key places:** Kabul (Zawahiri strike; al-Turkistani; low-level AQ sheltering), Helmand (Asim Umar; Marjah), Panjshir (AQ arms depot), Kunar/Nangarhar/Khost/Paktika (TTP camps; Haqqani heartland), Herat/Farah (AQ safe houses to Iran), Tehran (al-Masri killing; Haniyeh killing), Miram Shah/North Waziristan and Quetta (Haqqani/Quetta Shura bases, ep 6), Abbottabad, Doha, Puntland/Bari caves (Mumin).

**Notable dated events**
1. 2001-09 – Powell/Armitage seven demands to Musharraf (ep 6).
2. 2003-03 – KSM captured in Rawalpindi.
3. 2010-05-01 – TTP-backed Times Square plot (Faisal Shahzad).
4. 2018 – Taliban announce Jalaluddin Haqqani's death.
5. 2019-09 – AQIS emir Asim Umar killed in Helmand.
6. 2020-02-29 – US–Taliban Doha agreement.
7. 2020-08-07 – Abu Muhammad al-Masri and Miriam killed in Tehran (confirmed by NYT Nov 2020).
8. 2021-06-23 / 2021-08-06 / 2021-08 – Milley's district claims; Zaranj falls; Kabul falls, US partners with Badri 313.
9. 2022 – Zawahiri killed in Kabul; Saif al-Adel takes over unannounced.
10. 2024-03-22 – Khalid Saif al-Adel killed in Yemen; 2024-12-07 HTS takes Syria with TIP participation.

**Contradictions / revisions across episodes**
- Zawahiri: Dec 2020 rumors of natural death (ep 35) → UN "zero confirmation, assume alive" (ep 44) → killed in Kabul (ep 141).
- Succession: Saif al-Adel described as "only survivor of the line" (ep 35), then UN "warming up off the bench" (ep 44), then de facto emir (ep 141/238); Khalid Batarfi called a possible successor (ep 44) but reported arrested the same episode.
- AQ camps count: 6 provinces (2023 report) → 10 (ep 141, Feb 2024) → "at least 12" (ep 238, Feb 2025); Haqqani provinces (Paktia/Paktika/Khost) finally appear as TTP camp sites in 2025.
- Taliban–ISKP: ep 44 (UN) notes Haqqani presence inside ISKP; ep 238 hosts reject claims that the Taliban runs ISKP.
- Hosts' own slips: al-Masri death year said as 1998 (ep 44); Wuhayshi death "2013" (ep 141); Roggio's claim that AQAP's "general manager" Wuhayshi was killed in 2013 contradicts ep 35's June 2015 date.
- Roggio vs UN (ep 141): UN rates ISKP the greater external threat; Roggio argues AQ's Taliban-backed infrastructure is the greater long-term threat.
