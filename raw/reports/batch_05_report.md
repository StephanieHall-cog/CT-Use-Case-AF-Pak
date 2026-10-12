# Generation Jihad — batch_05 report

Pipeline: faster-whisper `distil-large-v3` (CPU int8, 8 vCPU, ~11x realtime) → `extract.py` (claude-sonnet-5-5) → analyst QA pass. Total audio 556 min; total transcription time 53.4 min.

## Episodes processed

| idx | Episode | Published | Audio (min) | Transcribe (min) | Extraction |
|---|---|---|---|---|---|
| 3 | Ep. 2 - Wishcasting in Afghanistan | 24 Mar 2020 | 22.5 | 2.0 | Claude |
| 17 | Ep. 16 - Al Qaeda's Never-ending Problems in Syria | 30 Jun 2020 | 70.2 | 6.9 | Claude |
| 41 | Ep. 40 — Al Qaeda in Iran – and Afghanistan | 15 Jan 2021 | 74.5 | 6.8 | Claude |
| 43 | Ep. 42 — Groundhog Day in Afghanistan | 03 Feb 2021 | 58.2 | 4.8 | Claude |
| 56 | Ep. 55 - Afghanistan Falls | 16 Aug 2021 | 47.7 | 4.0 | Claude |
| 75 | Ep. 74 — Zawahiri in Afghanistan | 01 Aug 2022 | 25.4 | 2.0 | Claude |
| 84 | Ep. 83 — Al Qaeda and Abu Huzaifah al Sudani | 04 Nov 2022 | 56.1 | 4.7 | Claude |
| 97 | Ep. 96 — New UN report on al Qaeda and the Islamic State | 02 Aug 2023 | 91.0 | 10.2 | **manual** |
| 101 | Ep. 100 — Squad Pops Off on Mali | 27 Sep 2023 | 47.3 | 5.0 | **manual** |
| 202 | Ep. 210 — 23 years since 9/11 | 11 Sep 2024 | 63.5 | 7.0 | **manual** |

Totals after QA: 200 persons, 212 organizations, 169 places, 191 events, 375 relationships (all relationships carry a quote + timestamp; no presenter person entries remain).

## Failures / deviations (none fatal)
- **Anthropic credits ran out** mid-batch (`credit balance is too low`, after 7 episodes). Per the fallback rule, idx 97, 101 and 202 were extracted **by hand** from the transcripts into the same schema (scripts kept in `qa/manual/`). They are complete but naturally sparser in orgs/places than Claude output; every item cites a transcript timestamp.
- `extract.py` needed two parameter changes to avoid silent truncation: chunk size 60 000 → 24 000 chars and `max_tokens` 16 000 → 32 000. Chunk 1 of idx 17 and 84 had hit `max_tokens` and the "repair" step dropped most relationships (idx 17: 20 rels → 73 after re-run). Output shape unchanged.
- The tty shell's `python3` resolved to pyenv 3.12 (no faster-whisper); ran with the 3.14 interpreter explicitly. No download failures; no `small.en` fallback needed.
- QA fixes applied (`qa/fix.py`, 40 edits): merged duplicate person entries (Abu Humam al-Shami, Rifai Ahmed Taha, Mohammed Islambouli, Abu Huzaifah al-Sudani, Nasir al-Wuhayshi); normalized names (Mullah Yaqoob, Mullah Omar, Abu Abd al-Karim al-Masri); removed host entries (Tom Joscelyn, Caleb Weiss); normalized `0MM:SS` timestamps; reversed 14 inverted relationships (e.g. "Taliban sheltered_by al-Qaeda" → al-Qaeda sheltered_by Taliban; "Iran trained_by al-Masri" → al-Masri trained_by Iran; person "leads" person → reports_to); retyped "leads al-Qaeda" for non-emirs to member_of; "Karam" → Kurram (inferred) for Hamza bin Laden's reported death site. Raw mis-hearings are preserved in `aliases`.
- Judgment calls flagged as `inferred`: Kurram for "Karam" (idx 41); "Al-Furqan office" for "Alfa Khan office" (idx 97); Ber for "Weir/Weirah" and Ghorak for "GORAC" (idx 101/202); William Shawcross for "short cross review" (idx 97). Hamza bin Laden's death is only "all indications" per Roggio.

## Analyst summary — networks revealed in these episodes

### Key individuals (role / affiliation / family)
1. **Ayman al-Zawahiri** — al-Qaeda emir 2011–2022. Hosts argued he was alive (Nov 2020 death claims rejected, idx 75) and probably under Haqqani protection in eastern Afghanistan/Pakistan (idx 41, Jan 2021). Killed by US strike 31 Jul 2022 at a **Haqqani guest house in Kabul** (idx 75, 97). Son-in-law **Abdul Rahman al-Maghrebi**.
2. **Saif al-Adel** — Egyptian; senior AQ leader freed by Iran in 2015, resident in Iran (idx 17, 41); "definitely in the running" to succeed Zawahiri (idx 84, Nov 2022); by Jul 2023 the de facto emir, still in Iran, unannounced because announcing him would contradict the Taliban's denial about Zawahiri (idx 97). **His son is inside Yemen in a key AQAP role** (idx 97). Received training from Iran/Hezbollah per 9/11 Commission (idx 41).
3. **Abu Muhammad al-Masri (Abdullah Ahmed Abdullah)** — AQ deputy emir, freed by Iran 2015, killed in Tehran 7 Aug 2020 by Israelis at US behest (idx 41).
4. **Abdul Rahman al-Maghrebi** — Moroccan; Zawahiri's son-in-law, long-time As-Sahab chief, AQ general manager; relocated to Iran (idx 41, 97). Recommended for deputy general manager by Atiyah in a bin Laden memo.
5. **Atiyah Abd al-Rahman** — bin Laden's general manager and liaison who negotiated the AQ–Iran facilitation agreement; killed 2011 (idx 41, 56, 84).
6. **Yasin al-Suri** — head of AQ's Iran facilitation network since ~2005 under an explicit agreement with the regime; still in Iran per State (idx 41).
7. **Sultan Yusuf Hasan al-Arif** — AQ operative designated Jan 2021, active in both Iran and Afghanistan (idx 41).
8. **Sirajuddin Haqqani** — Haqqani Network leader, Taliban deputy emir/number two (idx 43, 56), interior minister controlling passports (idx 75); reported former member of AQ's central shura; with father **Jalaluddin Haqqani** (d.) reunified the Taliban after the 2015 Mansour schism (idx 43, 97). Most likely host of Zawahiri in Kabul (idx 75).
9. **Hibatullah Akhundzada** — Taliban emir; called "emir of the faithful" by AQ (idx 3); ideological not military leader, formerly chief judge under Mansour (idx 84).
10. **Akhtar Mohammad Mansour** — second Taliban emir, "an al-Qaeda man" (idx 3), appointed 2015 after Mullah Omar's concealed 2013 death was disclosed (idx 43, 56).
11. **Mullah Yaqoob** — son of Mullah Omar, Taliban deputy emir (idx 75).
12. **Asim Omar** — AQIS emir and direct courier to Zawahiri, killed Sep 2019 in a Taliban compound in Helmand under a Taliban shadow governor's protection (idx 43).
13. **Husam Abd al-Rauf (Abu Muhsin al-Masri)** — AQ senior-management member killed in Afghanistan late 2020 on Taliban turf (idx 41, 43).
14. **Hamza bin Laden** — reportedly killed in Kurram, a Haqqani stronghold (idx 41).
15. **Abu Khalil al-Sudani** — AQ global-command member killed in a 2015 US raid in Barmal, Paktika (Haqqani territory); documents led to the Shorabak camps raid (150–200 AQ fighters killed) (idx 84).
16. **Abu Huzaifah al-Sudani** — veteran AQ ideologue (bin Laden companion, 2001 Saudi SAM plot under Atef/Saif al-Adel/Ibn al-Shaykh al-Libi, 2017 Syria reconciliation with al-Maqdisi and Abu Qatada); AQAP published his Sudan jihad manual; reportedly arrested in Sudan Nov 2022 (idx 84).
17. **Qari Baryal** — Kabul Attack Network commander who took IRGC money in Kabul and led the IED cell that killed Capt. Jesse Melton III (9 Sep 2008); now a Taliban governor (idx 202).
18. **Ali Qasim Salam al-Jaburi (Abu Sara al-Iraqi)** — head of ISIL's General Directorate of Provinces, the "shadow leader"; killed Feb 2023 (idx 97). ISIL caliph succession: Abu Ibrahim (Oct 2019–Feb 2022) → Abu al-Hasan (Feb–Oct 2022) → Abu al-Hussein (Oct 2022; Turkish claim of death Apr 2023 unconfirmed) → Abu Hafs (pledges by Aug 2023, idx 101).
19. **Abu Humam al-Shami (Farouq al-Suri)** — al-Faruq camp veteran, head of Hurras al-Din, broke with Julani in Jul 2016 (idx 17). **Sanafi al-Nasr** — bin Laden's third cousin, AQ Victory Committee head in Syria.
20. **Iyad ag Ghali** — Tuareg (Ifoghas) leader of Ansar Dine (AQIM front, 2012) and now JNIM emir, "al-Qaeda's man in the Sahel" (idx 17, 101).

### Key organizational relationships
- **Taliban ⇄ al-Qaeda**: never attacked AQ, zero raids since Doha (idx 3, 43); AQ embedded mentors/advisors, Haqqani–AQ joint unit funded by AQ (Treasury, idx 41/43); AQ fought for the Emirate (AQIS) and helped the Taliban fund-raise (idx 43); AQ "streaming into Kabul" with the Taliban (idx 56); AQ training camps across Afghanistan (idx 202). AQ cannot name Saif al-Adel emir without embarrassing the Taliban (idx 97).
- **Haqqani Network**: integral part of the Taliban holding many posts/shadow governorships; sheltered Zawahiri, Hamza bin Laden, Abu Khalil al-Sudani; strong back channels with **Iranian intelligence** (idx 97).
- **Iran ⇄ al-Qaeda**: working arrangement since the 1990s, 2011–2016 bipartisan US designations; hosted al-Masri, Saif al-Adel, al-Maghrebi, Yasin al-Suri; also episodic hostility (kidnappings, detentions, Syria/Yemen) (idx 41). By 2023 Iran "hosts the leadership of al-Qaeda including the leader" (idx 97).
- **Pakistan**: safe haven for Taliban/Haqqanis, LeT, JeM (State CRT 2019); redirects India-focused groups into Afghanistan; TTP is part of AQ's network (idx 17). By 2023 **TTP shelters in Afghanistan and uses an AQ-run camp in Kunar** (idx 97).
- **AQ global management is dispersed** (Iran, Yemen/AQAP, Syria/Hurras al-Din, Somalia/Shabaab, AfPak); AQAP's Batarfi possibly detained/released and ineffective; Shabaab (~$100M/yr) outranks AQAP (idx 41, 97).
- **Syria**: HTS/Julani dependent on Turkey vs. Hurras al-Din (AQ loyalists); Turkey sheltered senior AQ figures (Islambouli, Rifai Taha) (idx 17).
- **Sahel**: JNIM (AQIM sub-branch) controls much of northern/central Mali, encircling Bamako; IS Sahel holds Menaka; Tuareg CMA (MNLA, HCUA ex-Ansar Dine) retains ties to JNIM; Wagner is Bamako's patron (idx 101).

### Key places
Kabul (Zawahiri's Haqqani guest house; Kabul Attack Network); Kurram and North/South Waziristan (Pakistan tribal belt; 95% of US drone strikes); Kunar (TTP camp run by AQ); Helmand (Asim Omar killed); Paktika/Barmal and Shorabak, Kandahar (AQ camps 2015); Doha (Taliban office since 2013); Iran/Tehran (AQ leadership hub); Idlib (HTS/Hurras al-Din); Yemen (AQAP, Saif al-Adel's son); Menaka, Timbuktu, Bamako, Gao (Mali); Air Base 201 Agadez (US ISR); Sudan/Khartoum (1990s AQ base, Salama and Dinder cells).

### Notable dated events
1. 29 Feb 2020 — US–Taliban withdrawal agreement; 248 Taliban-claimed attacks in 28/34 provinces by 15 Mar 2020 (idx 3).
2. 12 Jun 2020 — Hurras al-Din-led "Stand Firm" operations room announced; HTS arrests follow (idx 17).
3. 7 Aug 2020 — Abu Muhammad al-Masri killed in Iran (idx 41).
4. Sep 2019 — Asim Omar (AQIS) killed in Helmand alongside Taliban commanders (idx 43).
5. 15 Aug 2021 — Kabul falls; Taliban offensive began May 2021 (idx 56).
6. 31 Jul 2022 — Zawahiri killed in Kabul (idx 75, 97).
7. Nov 2022 — AQAP publishes Abu Huzaifah al-Sudani's Sudan manual; his arrest in Sudan reported (idx 84).
8. Feb 2023 — ISIL GDP chief al-Jaburi killed; 25 Jul 2023 UN MT 32nd report (idx 97).
9. Jul–Sep 2023 — Niger coup; JNIM siege of Timbuktu; IS Sahel takes Menaka province; Tuareg CMA shoots down Malian aircraft (idx 97, 101).
10. 22 Aug 2024 — Taliban vice-and-virtue decrees on women; ~28 Aug 2024 CIA deputy director calls Taliban a CT partner (idx 202).

### Contradictions / revisions across episodes
- **Zawahiri alive/dead**: hosts rejected Nov 2020 death claims (idx 75 recap) and in Jan 2021 placed him in Haqqani strongholds (idx 41); confirmed dead in Kabul Jul 2022 — vindicating the Haqqani-shelter thesis.
- **Who leads AQ**: Nov 2022 "Saif al-Adel in the running" (idx 84) → Jul 2023 treated as emir in Iran (idx 97); hosts admit the UN "most concentrated leadership committee" was in Iran even while Zawahiri lived, revising earlier emphasis on AfPak.
- **Hamza bin Laden**: idx 41 says "all indications" he was killed in Kurram; not revisited.
- **Threat ranking**: Roggio explicitly disputes the UN (idx 97) that ISKP is the top threat in Afghanistan; Fitton-Brown half-agrees (TTP > ISKP) but defends the UN's inability to label the Taliban terrorists.
- **Mali IS–AQ truce**: reported truce vs. JNIM's same-day denial (idx 101) — recorded as unconfirmed.
- **Mullah Omar's death**: idx 56 dates it to 2013; idx 43/97 discuss the 2015 disclosure and Haqqani role in reunification — consistent, but the US embassy closure date Bailey gives ("2020", idx 202) is her recollection, not verified.
