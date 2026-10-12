# Generation Jihad — batch_10 report

**Pipeline.** Whisper `distil-large-v3` (CPU int8, 8 vCPU, ~7.5x realtime; 542 min of audio transcribed in ~74 min, no download failures). Extraction: idx 7 and 46 were extracted by `extract.py` (claude-sonnet-5-5) before the shared Anthropic account returned `credit balance is too low` on every call; the remaining seven episodes (49, 95, 157, 166, 197, 227, 256) were **extracted manually** by the analyst reading the full transcripts and writing JSON to `schema.json` (every mention/relationship/event carries a `[MMM:SS]` timestamp and quote; inferences marked `confidence: inferred`). `extract.py` was patched (24k-char chunks, max_tokens 32000) per sibling-batch advice but could not be re-run; idx 7 originally hit max_tokens (13 relationships) so 13 relationships, 3 organizations were added by hand from the transcript and two non-actors (Ken Burns, producer Phil Hegseth) removed. Analyst pass also normalised names (Sirajuddin Haqqani, Hibatullah Akhundzada, Mullah Yaqoob, Abdul Ghani Baradar, Qari Baryal, Tajmir Jawad, Abu Ikhlas al-Masri, Sanaullah Ghafari, Khalid Saif al-Adel …) keeping ASR mis-hearings in `aliases`, and flagged guests (Fitton-Brown, Dunleavy, Selber, Massoud, Daoud, Sharawi) with `is_presenter_or_guest`.

| idx | Title | Date | Audio | Whisper time | Extraction | P/O/Pl/E/R |
|---|---|---|---|---|---|---|
| 7 | Ep. 6 - Hezbollah's Main Man in Iraq | 21 Apr 2020 | 51 min | 6.5 min | Claude (+manual fix) | 27/30/23/21/26 |
| 46 | Ep. 45 — President Biden's Decision Points | 01 Mar 2021 | 54 min | 6.9 min | Claude | 9/10/6/5/7 |
| 49 | Ep. 48 — What happens in Afghanistan doesn't stay in Afghanistan | 19 Apr 2021 | 64 min | 8.2 min | manual | 22/17/14/12/23 |
| 95 | Ep. 94 — Al Qaeda has key roles in Taliban's Afghanistan | 15 Jun 2023 | 83 min | 10.7 min | manual | 19/23/14/14/43 |
| 157 | Ep. 156 — Is global jihad having a 'comeback'? | 03 Apr 2024 | 44 min | 6.0 min | manual | 10/19/20/12/20 |
| 166 | Ep. 166 — Bill and Tom's Excellent Debunking | 10 May 2024 | 60 min | 9.3 min | manual | 21/14/9/16/22 |
| 197 | Ep. 202 — History doesn't have to repeat itself in Afghanistan | 16 Aug 2024 | 83 min | 12.5 min | manual | 27/16/7/12/18 |
| 227 | Afghanistan's National Resistance leader | 23 Dec 2024 | 69 min | 8.9 min | manual | 15/17/11/11/24 |
| 256 | From Al-Qaeda to the Abraham Accords? | 01 Jul 2025 | 34 min | 4.6 min | manual | 12/15/8/10/14 |

Totals: 162 persons, 161 organizations, 112 places, 113 events, 197 relationships. Failures: none. Caveats: idx 46 is a policy episode with few named actors (9 persons is genuine, not truncation); idx 256 is Syria/Israel-focused (AfPak content limited to Roggio's AQ-estimate aside).

## Analyst summary — networks revealed in these episodes

**Key individuals**
1. **Sirajuddin Haqqani** — Taliban deputy emir + de facto interior minister; son of Jalaluddin; leads Haqqani Network; issues passports/IDs (UN: given to AQ members); Zawahiri killed in his Kabul guesthouse (Jul 2022); runs meth labs in eastern Afghanistan; former Miram Shah shura head; "kingmaker not king" (ep 94). Hibatullah owes him for reuniting the Taliban in 2015 (ep 94).
2. **Jalaluddin Haqqani** — founder; CIA-aided in 1980s, "in bed with" bin Laden, incubated first-generation AQ, helped bin Laden escape Tora Bora 2001 (ep 48).
3. **Hibatullah Akhundzada** — emir ruling from Kandahar; inaccessible; inferred to have known of Zawahiri's presence (ep 166); Dec 2024 decree barring women from medicine (ep 227).
4. **Mullah Yaqoob** — defense minister, deputy emir, son of Mullah Omar; "Kandahari" yet one of two senior Taliban who knew Zawahiri's location; sent Khalilzad a "no military solution" letter (ep 166).
5. **Ayman al-Zawahiri** — AQ emir; killed Jul 2022 in Haqqani safe house; AQ still silent two years later to spare the Taliban (ep 156).
6. **Saif al-Adel** — presumed AQ leader, sheltering in Iran; son **Khalid Saif al-Adel**, an AQAP leader, reported dead in a fire in Yemen (Mar 2024) — hosts suspect a possible faked death alongside **Khalid Batarfi**'s reported illness death (ep 156).
7. **Qari Baryal** — Taliban governor of Kapisa / northern zone commander; ex-Kabul Attack Network co-leader; took IRGC-QF money; UN lists as AQ-associated (ep 94).
8. **Tajmir Jawad** — deputy chief of Taliban intelligence, reports to Siraj; ex-Kabul Attack Network; AQ-associated (ep 94).
9. **Hafiz Hakim** — Taliban governor of Nuristan; AQ-associated; reported to **Mullah Abdul Qayyum Zakir** (ex-Guantanamo, Taliban southern commander) (ep 94).
10. **Abu Ikhlas al-Masri** — AQ commander freed from Bagram, rebuilt cadre/camp in Kunar–Nuristan (ep 94).
11. **Sanaullah Ghafari** — ISKP emir, ex-Haqqani Network member; unconfirmed death mid-2023 (ep 94).
12. **Hakimullah Mehsud / Baitullah Mehsud / Mullah Sangeen Zadran / Tahir Yuldashev** — TTP video shows a 2009-era "deputies meeting" of TTP, Haqqani (Sangeen = Siraj's deputy) and IMU/AQ (ep 6).
13. **Asim Umar** — AQIS emir sheltered by the Mullah Dadullah Front in Helmand when killed 2019 (ep 6).
14. **Zalmay Khalilzad** — Doha architect; 2016 testified Taliban would never break with AQ, 2018 claimed the opposite; told HFAC (Nov 2023) AQIS "doesn't exist anymore"; Afghans call him *Watan Furush* (eps 166, 202).
15. **Ahmad Massoud** — NRF leader, son of Ahmad Shah Massoud (killed by AQ 9 Sep 2001); offered Taliban foreign ministry; describes AQ intermarriage with Taliban elites (ep 227).
16. **Abdul Rahman al-Logari** — ISIS-K Abbey Gate bomber, 2017 CIA–India capture freed by Taliban from Parwan (ep 202).
17. **Ahmad al-Sharaa** — ex-AQ emir now Syrian president; HTS still FTO; family from Golan (ep 256).

**Organizational relationships.** Taliban–AQ "strong and symbiotic" (UN 14th report): welfare payments, passports, AQ appointees in MoD/intelligence; AQIS dual-hatted inside the emirate. Haqqani Network is integral to the Taliban (not a separable "gangster" faction) and may use ISKP as a cutout. TTP (~6,000 in Afghanistan, 40–50 groups joined 2023–24, Hafiz Gul Bahadur group effectively merged) is sheltered by the Taliban and attacks Pakistan, which nonetheless keeps backing the Taliban for strategic depth (endured ~100,000 dead 2007–15). AQ "localized" jihad via Taliban/TTP/Jamaat Ansarullah/IMU franchises (Massoud). ISKP (4–6k, doubled) is a rival to the Taliban but Massoud says most IS in Afghanistan (e.g. Kunduz) is Taliban-aligned. Al-Karrar office (Puntland) funds ISKP ~$25k/month. Iran/IRGC-QF funded Taliban attacks (Baryal) and runs narcotics with Mullah Naim Barich; shelters Saif al-Adel. Resistance: NRF, Afghanistan Freedom Front (Yasin Zia), Afghanistan United Front (Sami Sadat), Green Trend (Saleh) — "horizontal unity".

**Key places.** Kabul (Zawahiri safe house; Abbey Gate), Kandahar (Hibatullah; Shorabak AQ camp raid 2015), Kapisa/Nuristan/Kunar (AQ-linked governors, camps), Paktika/Paktia/Khost (Haqqani strongholds, AQ's first camps, UN data gap), Panjshir (NRF home; AQ weapons depot; fell 6 Sep 2021), Miram Shah, Bagram/Parwan prison, Doha, Rawalpindi GHQ, Puntland.

**Notable dated events.** 9 Sep 2001 AQ kills Ahmad Shah Massoud · 2001 Jalaluddin helps bin Laden out of Tora Bora · 10 Apr 2020 $10M reward for Kawtharani · 14 Apr 2020 TTP tribute video · 29 Feb 2020 Doha deal (Section 1F) · 15 Aug 2021 Kabul falls, Taliban offer to let US secure Kabul rejected · 26 Aug 2021 Abbey Gate · 6 Sep 2021 Panjshir falls (<1,000 vs ~35,000 incl. TTP/Arab AQ) · 31 Jul 2022 Zawahiri killed · Jun 2023 UN 14th report · 8 Nov 2023 Khalilzad HFAC interview · 22 Mar 2024 Crocus attack · Mar 2024 Pakistani strikes in Paktika/Khost · Aug 2024 Dunleavy resigns · Dec 2024 medicine ban decree · May–Jun 2025 Trump–al-Sharaa meeting and sanctions lift.

**Contradictions / revisions.** (a) Ep 48 (Bill) vs ep 166 (Tom) each claim authorship of the 2018 "The War in Afghanistan is Over, We Lost" article. (b) Ep 94: Roggio disputes the UN's emphasis on a Baradar–Haqqani feud and Hibatullah sidelining others, while accepting the "Taliban stays cohesive" conclusion. (c) Khalilzad's own reversal (2016 "never break with AQ" → 2018 "will break") is documented in ep 166. (d) AQ provincial footprint grows across episodes: UN 10 provinces (ep 166, Bill says ≥13), Selber cites 12 (ep 227), Roggio 10 + madrasas in 5 (ep 156). (e) ISKP leader Ghafari's death unconfirmed in ep 94; Saif al-Adel's son's death doubted in ep 156. (f) Ep 202's Dunleavy credits Milley/McKenzie with correct advice on 2,500 troops while the earlier episodes treat military leadership as uniformly delusional.
