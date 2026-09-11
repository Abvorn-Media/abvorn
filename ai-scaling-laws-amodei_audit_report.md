# Audit Report: `ai-scaling-laws-amodei` SKILL.md

**Audited file:** `C:\Users\Jean Mare\.agents\skills\ai-scaling-laws-amodei\SKILL.md`
**Date:** 2026-09-03
**Method:** Full factual verification of every claim against primary sources (Amodei's essays "Machines of Loving Grace" [Oct 2024], "The Adolescence of Technology" [Jan 2026], the Dwarkesh Podcast episode "We are near the end of the exponential" [Feb 13 2026], and the METR paper Kwa et al. 2025), plus internal-consistency and structure/quality review.

---

## 1. Verdict

The skill is **broadly accurate and well-structured** on substantive technical content. Almost all scientific/factual claims check out against primary sources. However, the document contains a **systematic dating error** (the Adolescence essay and the Dwarkesh podcast are both from **2026**, not 2025 as cited throughout), plus **one substantive factual error** (the bottleneck-factors table), and **one inaccurate METR statistic**.

**No critical safety/capability claims are fabricated.** The errors are citation/dating and one content substitution.

---

## 2. Critical Finding: Systematic 2025 → 2026 Dating Error

Both key 2026 sources are mis-dated as "2025" throughout the document.

| Location | Skilled claim | Actual |
|---|---|---|
| Intro (L8) | "The Adolescence of Technology" and "Dwarkesh Podcast, 2025–2026" | Adolescence essay is **Jan 2026**; podcast is **Feb 13 2026**. The "2025–2026" range is wrong — both are 2026. |
| Core Thesis (L21) | "(Dwarkesh Interview, 2025)" | Podcast published **Feb 2026** |
| Verifiable tasks (L106) | "(Dwarkesh Interview, 2025)" | **Feb 2026** |
| Key Quotes (L152, 154, 156) | "The Adolescence of Technology, 2025" | Essay is **Jan 2026** |
| Key Quotes (L160) | "(Dwarkesh Podcast, 2025)" | **Feb 2026** |
| Sources (L165) | "The Adolescence of Technology. (2025)" | **(2026)** |
| Sources (L167) | "Dwarkesh Podcast... (2025)" | **(2026)** |

The essay's own header reads **"January 2026"**. The Dwarkesh episode was published **February 13, 2026**. All three Adolescence Key Quotes (scaling laws, "few years before AI is better than humans", feedback loop) are **verbatim confirmed** in that essay — only the year is wrong.

**Fix:** Replace every "2025" associated with these two sources with "2026."

---

## 3. Substantive Factual Error: Bottleneck-Factors Table

**Section: "Bottleneck Framework" (L57–71).** The skill's table of "Complementary Factors (Bottlenecks)" lists five rows:
1. Speed of the outside world ✅
2. Human constraints ✅
3. Physical laws ✅
4. Data availability ✅
5. **Hardware** ❌ **should be "Intrinsic complexity"**

In "Machines of Loving Grace" (Oct 2024), Amodei explicitly names **five** factors that limit/complement intelligence:
1. **Speed of the outside world**
2. **Need for data**
3. **Intrinsic complexity** ← **omitted by the skill**
4. **Constraints from humans**
5. **Physical laws**

"Hardware" is **NOT one of the named factors** — Amodei mentions hardware only as an *example* inside the "speed of the outside world" discussion. The skill **replaced "Intrinsic complexity" with "Hardware"**, distorting the framework. "Intrinsic complexity" is a distinct and important Amodei concept (the idea that some problems are inherently hard regardless of intelligence).

**Fix:** Replace the "Hardware" row with "Intrinsic complexity" (long-run malleability: low — some complexity is irreducible).

---

## 4. Inaccurate METR Statistic

**Section: "Task Horizon Doubling" (L80).** The skill claims:

> "**2024–2025 acceleration:** Doubling time may have shortened to ~4 months"

The METR paper (Kwa et al., "Measuring AI Ability to Complete Long Tasks," 2025) reports:
- Overall (over ~6 years / since 2019): doubling ~every **7 months** ✅ (skill's L78 correct)
- **2023–2025: ~5.5 months**
- **2024-only: ~3 months**

The **"~4 months" figure is not in the paper.** It appears to be a conflation of the 5.5- and 3-month figures.

**Fix:** Change "~4 months" to reflect the paper's actual numbers — e.g. "2024-only data shows much faster doubling (~3 months), and 2023–2025 ~5.5 months." (Note L83 already correctly states "2024-only data shows faster doubling (~3 months)" — so the ~4-month figure in L80 is also **internally inconsistent** with the skill's own caveat.)

---

## 5. Verified as CORRECT (with confirmation detail)

| Claim | Verification |
|---|---|
| "Seven factors" (compute, data quantity, data quality/distribution, training duration, objective function, normalization/conditioning, architecture) | Confirmed in the Feb 2026 podcast's recap of the 2017 "Big Blob of Compute" doc: raw compute, data quantity, data quality/distribution, training duration, scalable objective functions, normalization/conditioning/numerical stability ("flows in this laminar way"), symmetries/architecture. Skill is accurate. |
| "5+ orders of magnitude with physics-level precision" | Substantively correct — 2026 podcast "across many orders of magnitude of compute"; 2023 podcast "predictable even to several significant figures which you don't see outside of physics." Not a verbatim single quote but a fair paraphrase. |
| "smooth, unyielding increase in AI's cognitive capabilities" + "hitting a wall" sentiment | **Verbatim in the Adolescence essay (2026)**. Correct. |
| Two phases / RL quote (L38) | Matches the 2026 podcast ("RL scaling now shows the same log-linear improvements seen in pretraining"). |
| Powerful-AI definition (5 properties, L46–51) | All 5 confirmed verbatim in "Machines of Loving Grace": Nobel-tier across fields, all interfaces, hours/days/weeks autonomous tasks, millions of instances, 10x–100x speed. Correct. |
| "country of geniuses in a datacenter" metaphor | Verbatim in Machines essay. Correct. |
| "compressed 21st century," "50–100 years of biological progress in 5–10 years" | Verbatim in Machines essay. Correct. |
| Timeline: "90% within 10 years; 50% within 1–3 years" (L15) | Confirmed in 2026 podcast: "I'm at 90% on that" (10 yrs); "a hunch—more like a 50/50 thing—that it's going to be more like one to two, maybe one to three." Correct. |
| "99%, 95%... 10 years... super safe bet" (L160) | Verbatim in 2026 podcast. Correct (only the "2025" date is wrong). |
| Verifiable / non-verifiable tasks (L108–109) | Confirmed verbatim in 2026 podcast ("There's no way we will not be there in ten years" for coding; "Hard to verify those tasks... a little bit uncertainty" for non-verifiable). Correct. |
| Feedback loop quote (L115) | Verbatim in the Adolescence essay (2026). Correct source; un-dated in-doc. |
| METR: ~7-month doubling, ~50 min Claude 3.7 Sonnet, ~11 data points / 6 years, 2028–2031 extrapolation (L78–83) | All correct per the paper. |
| "training compute doubled every ~3.4 months, 2012–2018" (L35) | Correct, matches Amodei & Hernandez "AI and Compute" (2020). |

---

## 6. Internal Consistency

Mostly consistent. Observations:

1. **L80 vs L83 tension:** "~4 months" (L80) contradicts the skill's own caveat "2024-only data shows faster doubling (~3 months)" (L83). The ~4-month figure is the loose end and should be removed as it is also factually wrong (see §4).
2. **L15 vs L160:** "90% within 10 years / 50% within 1–3 years" vs "99%, 95%... 10 years" — both are genuine, distinct confidence statements from different points in the 2026 podcast, so there is no contradiction. They are properly contextualized.
3. **Duplicated decision tree:** The capability ladder appears twice in near-identical form (L93–99 and L130–138). Not an error, but a redundancy; could be consolidated.
4. **Attribution gap:** "Steam Engine Mistake" (L87) and "Build Products That Don't Quite Work Yet" (L90) are presented as Amodei views without an in-doc source citation. They are real Amodei talking points but un-sourced within the skill.
5. **Year range in header (L8)** "Dwarkesh Podcast, 2025–2026" is inaccurate — the only cited podcast episode is Feb 2026.

---

## 7. Structure & Quality

**Strengths:**
- Clear logical arc: who → thesis → training phases → capability framework → bottlenecks → task horizon → product strategy → uncertainty → action.
- Actionable "How to Apply" (5 concrete steps) and a "Guardrails" section that correctly cautions against over-extrapolation — notably aligned with the sources' own caveats.
- Good use of tables and decision trees; the task-horizon/capability-timing content is genuinely useful for product decision-making.
- Correctly flags the METR extrapolation caveat and the ~11-data-point fragility.

**Weaknesses:**
- **Dating errors (critical)** — see §2. This is the single biggest quality problem because it is systematic and makes the skill look out-of-date/wrong.
- **One content substitution** in the bottleneck table (§3) that misrepresents Amodei's actual framework.
- Minor redundancy (decision tree duplicated) and a couple of unsourced-inline attributions (§6).

---

## 8. Recommended Corrections (priority order)

1. **Fix all "2025" → "2026"** for "The Adolescence of Technology" (L8, 152, 154, 156, 165) and the Dwarkesh podcast (L21, 106, 160, 167).
2. **Fix the bottleneck table**: replace "Hardware" with **"Intrinsic complexity"** (L69).
3. **Fix the METR statistic**: change "may have shortened to ~4 months" to the paper's real figures — "2024-only data shows ~3 months; 2023–2025 ~5.5 months" (L80).
4. Optionally: fix header year range to "Dwarkesh Podcast (2026)" (L8); add source citations for the steam-engine and build-now claims; consider consolidating the duplicated decision tree.

---

## 9. Sources Checked

- Amodei, "Machines of Loving Grace" (Oct 2024) — full text — darioamodei.com
- Amodei, "The Adolescence of Technology" (Jan 2026) — full text — darioamodei.com/essay/the-adolescence-of-technology
- Dwarkesh Podcast, "Dario Amodei — We are near the end of the exponential" (Feb 13, 2026) — transcript via dwarkesh.com / steadcast.co
- Kwa et al., "Measuring AI Ability to Complete Long Tasks" (METR, Mar 2025) — metr.org
- Amodei & Hernandez, "AI and Compute" (2020) — for the 3.4-month doubling figure

*Note: the skill's cited URL for the Adolescence essay (`darioamodei.com/essay/the-adolescence-of-technology`) was verified as working; the alternative path `/the-adolescence-of-technology` 404s.*
