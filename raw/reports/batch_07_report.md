# Batch 07 report — Generation Jihad (FDD Long War Journal)

## Episodes processed

| idx | title | published | duration (min) | transcription (min) | extraction |
|---|---|---|---|---|---|
| 16 | Ep. 15 - Don't Call It Nation-Building | 23 Jun 2020 | 58 | 11.6 | Claude (extract.py) |
| 32 | Ep. 31 - Al Qaeda's Media Chief Killed in Taliban Country | 29 Oct 2020 | 55 | 11.0 | Claude (extract.py) |
| 51 | Ep. 50 — The Unknowns | 04 Jun 2021 | 68 | 14.6 | Claude (extract.py) |
| 76 | Ep. 75 — Zawahiri is dead. Al Qaeda is not. | 05 Aug 2022 | 79 | 15.7 | manual |
| 181 | Ep. 181 — Al Qaeda's leader has a new rallying cry. We should listen. | 18 Jun 2024 | 49 | 9.6 | manual |
| 186 | Ep. 186 — A conversation with Lieutenant General Sami Sadat | 02 Jul 2024 | 86 | 16.4 | manual |
| 199 | Ep. 204 — Three years after the fall of Kabul | 21 Aug 2024 | 63 | 12.8 | manual |
| 285 | "Trust Me, Bro" and The Art of Verification | 11 Dec 2025 | 40 | 5.3 | manual |
| 339 | The UN Monitoring Team's latest report: Where the global jihad stands now | 02 Sep 2026 | 44 | 3.5 | manual |

Transcription: faster-whisper `distil-large-v3`, CPU int8, 8 threads, ~5x realtime (547 min of audio in ~101 min). No episode failed; no model downgrade needed.

Extraction: `extract.py` (Claude) completed idx 16, 32, 51. From ~04:35 UTC the Anthropic API returned "credit balance is too low" (account-wide); a retry loop ran to the end without success, so idx 76, 181, 186, 199, 285 and 339 were extracted **manually** by reading each transcript and hand-writing the schema JSON. Per sibling-batch feedback, `extract.py` was patched (chunk 24k chars, max_tokens 32000) before the retry loop; idx 16 had hit max_tokens on one chunk under the old settings, but at 31 relationships/58 min it is above the ~4-per-10-min re-run threshold and was hand-checked instead of re-run. Idx 199 has the lowest density (17 relationships/63 min) because it is largely a political post-mortem of the Republic's collapse rather than a network episode.

Quality pass applied to all nine files: canonical spellings (Sirajuddin Haqqani, Hibatullah Akhundzada, Ayman al-Zawahiri, Saif al-Adel, Abdul Ghani Baradar, Mullah Yaqoob, Husam Abd al-Rauf, Abdul Rahman al-Maghrebi, Hakimullah Mehsud) with ASR misspellings kept in `aliases`; presenters flagged `is_presenter_or_guest`; every relationship has a timestamp and quote; duplicate (source,target,type) relationships and near-duplicate events merged. Relationship endpoints such as "United States", "NDS", "As-Sahab", "Africa" are used as targets without a matching entity record in a few files (same convention as the Claude output); the merge step should treat them as organizations/places.

Totals: 195 persons, 160 organizations, 136 places, 140 events, 285 relationships (summed across the nine files).

## Analyst summary

### Key individuals (role / affiliation / family)

1. **Ayman al-Zawahiri** — al-Qaeda emir; located "eastern Afghanistan" per CENTCOM (ep 16, 2020); killed by US drone 31 Jul 2022 in a Kabul safe house run by Sirajuddin Haqqani's people (ep 76, 181, 285). Al-Qaeda has never announced his death or a successor (ep 285).
2. **Sirajuddin Haqqani** — head of the Haqqani Network, Taliban deputy emir and interior minister; son of Jalaluddin, brother of Anas; sheltered Zawahiri; livestreamed Hajj with Anas June 2024 (ep 181/186). Sadat (ep 186) says he directs the Taliban suicide apparatus and alleges Haqqani-ISKP links.
3. **Jalaluddin Haqqani** — Haqqani Network founder; helped bin Laden escape Tora Bora late 2001 (ep 51).
4. **Anas Haqqani** — Siraj's brother; Doha negotiator (ep 51, 181, 186).
5. **Saif al-Adel** — al-Qaeda deputy/military chief based in Iran since 2015 release (ep 51, 76); de facto emir after Zawahiri, unannounced because he sits in Iran (ep 181); "head of al-Qaeda's global operations" (Sadat, ep 186).
6. **Abdul Rahman al-Maghrebi** — Zawahiri's son-in-law; heads As-Sahab / external communications; Iran-based; third in UN seniority line (ep 51, 76).
7. **Abu Muhammad al-Masri** — AQ deputy emir, Iran-based, assassinated Aug 2020 by Israel with CIA help (ep 51).
8. **Hamza al-Khalidi** — head of AQ military committee, Iran-based per 2016 Treasury designation (ep 51).
9. **Husam Abd al-Rauf (Abu Muhsin al-Masri)** — AQ media chief (As-Sahab / Vanguards of Khorasan editor), killed by Afghan NDS in Taliban-controlled Andar district, Ghazni, Oct 2020 (ep 32).
10. **Asim Umar** — first AQIS emir, killed in US-Afghan raid in Taliban stronghold Musa Qala, Helmand, Sep 2019 (ep 16, 32, 51); **Osama Mahmood** probable successor (ep 51).
11. **Hibatullah Akhundzada** — Taliban emir; receives al-Qaeda bay'ah (ep 76, 181, 186).
12. **Mullah Yaqoob** — Mullah Omar's son, defense minister (ep 76, 181). **Abdul Ghani Baradar** — now a Taliban deputy (ep 199).
13. **Abdelmalek Droukdel → Abu Obeida Yusuf al-Annabi / Yazid Mebrak** — AQIM succession after Droukdel's June 2020 death in Mali (ep 16, 51, 76).
14. **Abdul Haq al-Turkistani** — TIP leader and AQ shura figure; presumed dead c.2012-14, resurfaced; TIP re-based in Baghlan (ep 51, 76, 285).
15. **Hamza bin Laden** — Osama's son; US announced death 14 Sep 2019; al-Qaeda eulogized him; Dec 2025 "proof of life" video was an AI hoax (ep 285).
16. **Hakimullah Mehsud** — TTP emir falsely reported dead 2009, proven alive via 2010 Times Square plot video, later killed by US drone (ep 285).
17. **Sami Sadat** — ex-ANA 215 Corps/Special Operations commander; leads the Afghanistan United Front; claims a far larger AQ presence than the UN (ep 186, 199).
18. **Colin Smith / Edmund Fitton-Brown** — successive UN Monitoring Team coordinators (ep 76, 339).
19. **Sanaullah Ghafari** — ISKP emir (ep 186); **Hafiz Saeed Khan** — first ISKP emir, ex-TTP Orakzai (ep 186).
20. **Mahdi Arsalan** — Jamaat Ansarullah commander controlling five Badakhshan districts (ep 76); **Qari Fasihuddin** — Taliban army chief, Tajik from Badakhshan (ep 76).

### Key organizational relationships
- Taliban ⟷ al-Qaeda: sheltering/safe haven stated in every Taliban-era episode; AQ training camps in Haqqani areas (Paktia, Paktika, Khost), media/weapons depot in Panjshir (ep 181); "part of the government" (ep 285).
- Haqqani Network ⊂ Taliban; hosted Zawahiri; alleged ISKP links (Sadat, ep 186 — single-source).
- Iran hosts AQ senior leadership (Saif al-Adel, al-Maghrebi, al-Khalidi, al-Masri) (ep 51, 76, 181).
- AQIS, TIP, Jamaat Ansarullah, IMU, TTP operate under Taliban cover from Afghanistan (ep 76); TTP attacks in Pakistan surging in 2026 (ep 339).
- AQ global network: ~$50M JNIM ransom moved JNIM → AQIM → AQAP and AQ central leadership (ep 339); >25,000 AQ fighters, two-thirds in Africa.
- AQ vs Islamic State remain rivals (Sahel, Afghanistan, Syria), despite "merger" claims (ep 285).
- Afghanistan United Front (Sadat) and NRF (Ahmad Massoud) as anti-Taliban opposition (ep 181, 186, 199).

### Key places
Kabul (Zawahiri safe house, Sherpur); Andar/Ghazni (Rauf killed); Musa Qala & Helmand (Umar killed; Taliban centre of gravity, Sadat); Kunar (al-Qahtani killed 2016); Baghlan (TIP base); Badakhshan (Ansarullah); Panjshir (AQ media centre/depot); Paktia/Paktika/Khost (Haqqani camps); Shorabak, Kandahar (AQ camps raided Oct 2015); Iran (AQ leadership); Doha (talks); Bamako/Kati (JNIM 2026); al-Hol (15-20k unaccounted).

### Notable dated events
- Oct 2015 — Shorabak (Kandahar) AQ camp raid (ep 186).
- Oct 2016 — Faruq al-Qahtani killed, Kunar (ep 16).
- 14 Sep 2019 — Trump announces Hamza bin Laden dead (ep 285); Sep 2019 — Asim Umar killed, Musa Qala (ep 16/32/51).
- Jun 2020 — Droukdel killed in Mali; Khalid al-Aruri killed in Idlib (ep 16).
- Aug 2020 — Abu Muhammad al-Masri assassinated in Tehran (ep 51).
- Oct 2020 — Husam Abd al-Rauf killed, Andar, Ghazni (ep 32).
- 31 Jul 2022 — Zawahiri killed, Kabul (ep 76).
- ~7 Jun 2024 — Sirajuddin & Anas Haqqani Hajj in Saudi Arabia (ep 181/186).
- 15 Aug 2024 — Afghanistan United Front conference (ep 199).
- Dec 2025 — Hamza bin Laden AI-video hoax exposed (ep 285).
- 25 Apr 2026 — JNIM assault on Bamako/Kidal/Kati; May 2026 — IS deputy al-Maynuki killed (ep 339).

### Contradictions / revisions between episodes
- Droukdel is "second deputy" to Zawahiri in ep 16 but "third deputy" in ep 51 (both citing French officials).
- Zawahiri placed in "eastern Afghanistan" (ep 16, 2020) and believed by the UN to be in Afghanistan; killed in central Kabul (ep 76) — hosts stress this vindicated their Taliban-shelter thesis.
- Hamza bin Laden: ep 32 era treats him as dead; ep 285 revisits amid "alive" claims and concludes presumed dead but agnostic.
- AQ leadership: ep 76 lists Saif al-Adel as "possible successor"; ep 181/186 call him de facto leader; ep 285 notes AQ itself has never announced any successor.
- Scale of AQ in Afghanistan: Sadat (ep 186) claims far larger numbers than UN reporting; hosts flag but don't endorse. Ep 285 later criticises threat inflation by some Afghan opposition sources — a soft walk-back of the ep 186 framing.
- Nature of AQ: ep 339 reports some agencies view AQ as a mere "consultancy"/regional body; the ransom-flow evidence is offered to rebut this, consistent with the hosts' long-standing position.
- Haqqani–ISKP cooperation (ep 186) is Sadat's claim and is marked `inferred`/single-source; ep 285 rejects AQ–IS "merger" narratives.

Decisions: no questions were escalated; manual extraction used for 6 of 9 episodes per the fallback rule; non-AfPak episodes (285 on epistemology, 339 on the UN report) were extracted in full because they carry AfPak-relevant claims (Hamza, Zawahiri succession, TTP surge, 1988 regime).
