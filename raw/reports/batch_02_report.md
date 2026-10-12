# Generation Jihad — batch_02 report

**Pipeline.** faster-whisper `distil-large-v3` (CPU, int8, 8 threads, ~10-11x realtime); extraction with `extract.py` / `claude-sonnet-5-5`; analyst QA pass applied by `fix.py` + `patches.py` (name normalization with raw ASR spellings kept in `aliases`, chunk-overlap de-duplication, `MM:SS` timestamp repair, direction fixes on sheltered_by/hosted_by, missed family links added).

## Episodes processed

| idx | Title | Date | Audio | Transcribe | Extraction |
|---|---|---|---|---|---|
| 11 | Ep. 10 – Endless Jihad | 2020-05-19 | 72.2 min | 6.6 min | Claude |
| 12 | Ep. 11 – An Al Qaeda Sleeper Agent in Pensacola | 2020-05-26 | 49.4 min | 4.5 min | Claude |
| 14 | Ep. 13 – Send in the Military? | 2020-06-09 | 53.8 min | 4.7 min | Claude |
| 47 | Ep. 46 – Waiting for a withdrawal decision | 2021-04-05 | 40.1 min | 3.7 min | Claude |
| 83 | Ep. 82 – Zawahiri's successor and a Shabaab update | 2022-10-12 | 60.9 min | 5.6 min | Claude |
| 124 | Ep. 123 – The Afghanistan affliction | 2023-12-08 | 64.2 min | 5.8 min | Claude |
| 196 | Ep. 201 – New UN report on jihadi threat in Africa, Asia, Middle East | 2024-08-13 | 66.2 min | 5.7 min | Claude |
| 225 | Now hiring: moderate terrorists | 2024-12-18 | 44.3 min | 4.8 min | Claude |
| 295 | The West's greatest threat is still al Qaeda | 2026-02-10 | 96.1 min | 10.0 min | **manual** |

Totals after QA: 181 persons, 188 organizations, 190 places, 135 events, 286 relationships (every relationship has a timestamp and quote).

**Failures / calls made.**
- No transcription failures. One extraction chunk (idx 83) hit `max_tokens`; `extract.py`'s built-in JSON repair recovered it.
- **idx 295 was extracted by hand.** On the final `extract.py` run the Anthropic API returned `credit balance is too low` on every retry, so per the instructions I read the 96-minute transcript and wrote `extractions/295_*.json` to the same schema (21 persons, 30 orgs, 39 places, 19 events, 68 relationships, all with timestamps/quotes). Two events there (Kerman/Crocus attacks; Batarfi + Saif al-Adel's son deaths) have an empty `date` because the hosts never state one.
- Guest analysts (Edmund Fitton-Brown in 14 and 295; Stu Velasco and Zach Popp in 124) are kept as persons with `is_presenter_or_guest: true` because the hosts discuss their careers; regular presenters are excluded.
- idx 83: the transcript garbles the name of the third Iran-based AQ leader and the hosts correct themselves mid-sentence; I kept both Abu Muhammad al-Masri and Abu al-Khayr al-Masri with the raw spellings in aliases rather than guess.
- idx 225: the hosts say only that Khalil Haqqani "is a Haqqani" and attended by Sirajuddin; the uncle/nephew link is marked `inferred`.

## Analyst summary — networks revealed in these episodes

### Key individuals
1. **Saif al-Adel** (Egyptian) — de facto emir of al-Qaeda since Zawahiri's death; *guest of the Iranian government*, residing in Iran (started as house arrest). Visited Afghanistan at least once post-2021 via safe houses on the Afghan–Iranian border but lives in Iran (295). Son (unnamed) worked with AQAP in Yemen and died within a month of Batarfi (196, 295).
2. **Ayman al-Zawahiri** — AQ emir; sheltered in a Kabul safe house by the Haqqanis; killed by US strike 31 Jul 2022 (83, 295). Decided c.2012 to make the Shabaab bay'ah public (83).
3. **Sirajuddin Haqqani** — Haqqani Network leader, Taliban deputy emir / interior minister; US-designated with $10M bounty; AQ's closest Taliban ally; hosted Zawahiri (47, 83, 225, 295).
4. **Khalil ur-Rahman Haqqani** — senior Haqqani (uncle of Sirajuddin, *inferred*), Taliban minister; died Dec 2024; Hekmatyar attended funeral (225).
5. **Hibatullah Akhundzada** — Taliban emir; his son carried out a suicide bombing in Gereshk, Helmand c.2017 (12); receives Shabaab allegiance (11).
6. **Mullah Mohammad Omar** — Taliban founder; death concealed by Taliban ("weekend at Bernie's") (295); sheltered bin Laden (11); father of Mullah Yaqoob (83, 225).
7. **Mullah Yaqoob** — Taliban defense minister, son of Omar; weapons expo in Turkey Nov 2024 (225).
8. **Osama bin Laden** — killed Abbottabad 2011; files show he was directing affiliates, not a "lion in winter" (83, 295); father of Hamza bin Laden (14).
9. **Abu Mohammad al-Jolani / Ahmed al-Sharaa** — ex-AQ Syria branch leader, HTS; took Damascus Dec 2024; sanctions lifted, met Trump; hosts still treat him as at least an AQ ally (225, 295).
10. **Abdul Qadir Mumin** (Somali) — ex-Shabaab; heads ISIS-Somalia and the Al-Karrar office (ISIS finance hub); some UN member states believe he is overall ISIS caliph — hosts skeptical (196, 295).
11. **Abu Bakr al-Mainuki** (Nigerian) — head of ISIS Al-Furqan office (Lake Chad Basin); UN suggests he may now head the General Directorate of Provinces after **Abu Khadija** was killed in 2025 (295).
12. **Saad bin Atef al-Awlaki** (Yemeni) — AQAP emir succeeding **Khalid Batarfi** (Saudi, died); AQAP now allied with the Houthis (295).
13. **Qasim al-Rimi** — AQAP emir killed Jan 2020; **Mohammed al-Shamrani** — AQAP sleeper, Pensacola shooter Dec 2019; **Abdullah al-Maliki** — AQAP external-ops contact (12).
14. **Abu al-Khayr al-Masri / Abu Muhammad al-Masri / Saif al-Adel** — the Iran-based AQ leadership tier discussed as Zawahiri's successors (83).
15. **Mullah Akhtar Mansour** — Taliban emir killed by US strike in Pakistan 2016 (14). **Jehad Serwan Mostafa** — American AQ/Shabaab figure (83). **Ahmed Abdi Godane / Abdullah Yare** — Shabaab founders; Yare killed by US strike Sept 2022 (83). **Qari al-Tamim** — reported head of ISIS Al-Siddiq office in Afghanistan (295). **Gen. Abdul Raziq** — Kandahar police chief killed by Taliban 2018 (11, 124).

### Key organizational relationships
- **Taliban ⇄ al-Qaeda**: no break after the 29 Feb 2020 Doha deal; zero Taliban attacks on AQ; AQ endorses the Emirate; AQ camps in Dishu/Shorabak (Helmand) and Kandahar/Uruzgan; Taliban issue IDs to foreign fighters (11, 12, 47, 124, 225, 295).
- **Haqqani Network ⇄ al-Qaeda/AQIS**: AQIS commander killed in Haqqani-run territory; Zawahiri hosted by Sirajuddin in Kabul (47, 83).
- **Iran ⇄ al-Qaeda / Taliban**: Iran hosts Saif al-Adel; *Cabrera v. Iran* showed weapons, training, safe haven, intelligence to the "syndicate"; by 2026 Fitton-Brown says "Iran controls al-Qaeda"; AQ gets weapons from Houthis and IRGC (196, 295).
- **AQAP ⇄ Houthis ⇄ al-Shabaab**: new AQAP–Houthi alliance and a possible trilateral strategic meeting (295); AQAP external ops directed Pensacola (12).
- **al-Shabaab ⇄ al-Qaeda**: most loyal/effective branch, oath to Zawahiri and Hibatullah; pressed by Somali offensive and by ISIS-Somalia in the Al Miskaad mountains (11, 83, 196).
- **ISIS regional offices**: Al-Karrar (Somalia, finance incl. money linked to the Kabul-airport attack), Al-Furqan (NE Nigeria, West Africa/Sahel), Al-Siddiq (Afghanistan, co-located with ISKP); ADF (DRC) and Mozambique pledged to ISIS; ISKP recruits along Tajik/Central Asian diaspora lines (196, 295).
- **HTS / Hurras al-Din**: HTS was AQ's Syria branch; still supported Hurras al-Din in 2024; HaD "disbanded" Jan/Feb 2025 but cells remain in southern Syria (196, 225, 295).
- **JNIM / Ansaru**: AQ Sahel branch, ~40% of Burkina Faso (2024), fuel blockade of Bamako and expansion into Nigeria with Ansaru (196, 295). **Pakistan**: ISI support is why the Taliban were never beaten (11).

### Key places
Kabul (Zawahiri safe house); Helmand – Dishu, Shorabak, Gereshk, Sangin; Kandahar/Uruzgan (Route Bear, 2016); Kunar/Nuristan (AQ rat lines); Tora Bora; Doha; Abbottabad; Iran/Tehran and the Afghan–Iranian border safe houses; Yemen; Mogadishu, Jubaland, Al Miskaad/Puntland, Somaliland; Bamako, Burkina Faso, Lake Chad Basin/NE Nigeria; Idlib/southern Syria, al-Hol; Pensacola.

### Notable dated events
- 2019-12-06 Pensacola NAS shooting by AQAP sleeper al-Shamrani; AQAP claims Feb 2020 (12).
- 2020-01 US strike kills AQAP emir Qasim al-Rimi (12).
- 2020-02-29 US–Taliban Doha agreement; ~4,500 Taliban attacks in 45 days; fatwa ~7 Mar (11, 12, 47).
- 2016-10 Taliban cut Route Bear, isolating Uruzgan; 2018 Taliban kill Gen. Raziq in Kandahar (124, 11).
- 2022-07-31 US strike kills Zawahiri in Kabul in a Haqqani-provided house (83, 295).
- 2022-08/09 Hayat Hotel siege; Somali offensive; US strike kills Abdullah Yare (83).
- 2024-07 UN report; JNIM/Tuareg kill ~50 Wagner in Mali; 2023-08 Abu Hafs al-Hashimi named caliph (196).
- 2024-12 HTS takes Damascus; Khalil Haqqani dies; Yaqoob in Turkey (225).
- 2025 Abu Khadija (ISIS GDP head) killed; 2025-01/02 Hurras al-Din "disbands"; 2025-06 twelve-day war — Saif al-Adel stays in Iran; 2026-01 Syrian government attacks SDF; JNIM Bamako blockade and ~$50M ransom (295).

### Contradictions / revisions across episodes
- **Successor to Zawahiri**: in Oct 2022 (83) the hosts list three Iran-based candidates and hedge; by Aug 2024 (196) and Feb 2026 (295) Saif al-Adel is treated as de facto emir and the point of contention shifts to the UN refusing to name Iran as his location (196 said the report "avoids saying"; 295 says it is now the third consecutive report to omit it).
- **Saif in Afghanistan?** 196 raises UN reporting of possible travel; 295 settles it: trips yes, residence no, and he did not leave Iran during the June 2025 war.
- **Mumin as caliph**: both 196 and 295 doubt it; 295 adds a second African (al-Mainuki) as possible GDP head and reads the UN language as "farming out" member-state claims.
- **Hurras al-Din**: 196 says HTS still supports it; 295 says HaD fell out with HTS, many members killed/imprisoned, and it "disbanded" nominally.
- **AQAP–Houthi**: 196 frames it as a truce pushed by Saif's son that may have angered Yemeni jihadis; 295 upgrades it to an alliance and reads it as evidence of cohesion under Iran-based leadership, not a split.
- **AQ strength in Afghanistan**: 47 says UN's 400–600 is too low; 124's guests put 300–400 in Kandahar and 200–300 in Uruzgan alone, versus official 50–100.
- Hosts in 124 are unsure whether Raziq was killed in 2018 or 2019 (11 states Oct 2018).
