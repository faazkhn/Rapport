# Writing doctor questions for a simulated patient

Thank you for helping. You will write questions that a doctor might ask each of four simulated patients. Please do not look at the
simulator's code, its keyword lists or any earlier question set.

For each memory below, write lines a real doctor might say to this patient:
- at least 4 lines per memory, and at least 12 per **risk** memory;
- mix the ways people really ask: textbook, gentle and indirect, clumsy or leading, colloquial Indian English, euphemistic; if you
  naturally speak Hindi-English (Hinglish), please write some lines that way too;
- most lines should avoid the memory's obvious key words;
- each line must make sense on its own;
- also write some lines that ask about nothing (greetings, small talk, empathy only);
- label each line with every memory it asks about (ids below), and nothing more; mark lines you think are hard.

Return a spreadsheet with columns: `case`, `line`, `memory_ids` (comma-separated, empty for "nothing"), `hard` (yes/no).


## Case `mdd_01`: Ananya Rao, 24, female

Ananya Rao, 24, software test engineer, referred by the company doctor. Two months of tiredness and 'not being herself', several sick days recently. Physical check-up reported normal. Please assess.

| id | kind | what the patient knows |
|---|---|---|
| `f_pc` | symptom | Has felt tired all the time and 'not herself' for about two months. Came because the company doctor insisted after she took several sick days. |
| `f_onset` | history | It started about two months ago, a few weeks after she was moved to a new project with a demanding manager, and has slowly got worse. She has never felt like this before. |
| `f_mood` | symptom | Feels low and empty most of the day, nearly every day, worse in the mornings. Sometimes cries alone in the office washroom. |
| `f_anhedonia` | symptom | Has stopped her Carnatic singing practice and stopped calling college friends at weekends. Nothing feels enjoyable any more, not even watching films with her flatmate. |
| `f_sleep` | symptom | Falls asleep but wakes around 4 a.m. and cannot get back to sleep. Lies in bed till late at weekends without feeling rested. |
| `f_appetite` | symptom | Poor appetite, often skips dinner. Clothes feel loose; thinks she has lost about 4 kg in two months. |
| `f_energy_concentration` | symptom | Exhausted even after resting. Cannot concentrate: rereads the same test case many times, has made mistakes and missed two deadlines. |
| `f_guilt` | formative | Feels worthless and like a burden. Ashamed that she is 'weak' and feels she is failing her parents, who sacrificed a lot for her education. |
| `f_anxiety` | symptom | Feels tense and keyed up most days, worries constantly about losing her job, mind races at night, hands shake slightly before meetings. This started with the low mood, not before. |
| `f_work_family` | trigger | New manager criticises her in front of the team and her appraisal is next month; she fears losing the job. Sends about Rs 15,000 a month home for her brother Rohan's college fees. Her mother keeps bringing up marriage proposals on the phone, which adds pressure. Her family does not know how bad she feels. |
| `f_family_history` | history | A maternal aunt was 'on tablets for her nerves' for some years after a bad time; the family does not talk about it. No one in the family has had mood swings with very high periods, psychosis, alcohol problems or suicide as far as she knows. |
| `f_passive_si` | risk | For about the last three weeks, some nights she wishes she would just not wake up in the morning. The thoughts come a few times a week and pass. |
| `f_no_plan_no_attempt` | risk | She has no plan and no intention of ending her life, has never thought about how, has never harmed herself and has never attempted suicide. |
| `f_no_means` | risk | She has no stored tablets or other means at home and has not looked anything up. |
| `f_protective` | history | She could never do that to her mother and her brother Rohan, who looks up to her. Her flatmate is kind to her. She wants to feel better and would accept help. |
| `f_substances` | history | Drinks very rarely, maybe a glass of wine at an office party two or three times a year. Has never used cannabis, bhang or any other drug. Does not smoke or chew tobacco. Drinks two cups of filter coffee a day. |
| `f_no_psychosis` | symptom | Has never heard voices or seen things others cannot. Does not feel watched, followed or controlled. |
| `f_no_mania_no_psych_hx` | history | Has never had a period of days of feeling unusually high, overconfident or full of energy with little need for sleep. Has never seen a psychiatrist or counsellor or taken psychiatric medicine before. |
| `f_medical` | history | No medical illnesses, takes no regular medicines, no allergies. The company health check two weeks ago, which she was told included a thyroid test, was normal. No history of abuse or major trauma. |
| `f_pregnancy` | history | Periods are regular; last period ended about a week ago. Not sexually active, not pregnant, not on any contraception. |

## Case `alc_01`: Kavya Gowda, 33, female

Kavya Gowda, 33, sales manager, referred by the family physician for 'tremors and poor sleep'. Liver enzymes raised last month. Her spouse has come along and is waiting outside. Please assess.

| id | kind | what the patient knows |
|---|---|---|
| `f_pc` | symptom | Hands have been shaking and she sleeps badly. Came because her spouse insisted after she could not hold a cup steady at a family function last week. Wants 'something for the nerves and sleep'. |
| `f_drinking_minimised` | history | Says she has 'a couple of pegs in the evening, like everyone in sales'. |
| `f_drinking_quantity` | history | The real amount: about half a bottle (375 ml) of whisky every evening for three years, more at weekends; needs more now than before to feel the same. |
| `f_last_drink` | history | Last drink was around 10 last night, about twelve hours ago. Had nothing this morning because her spouse came along. |
| `f_morning_drinking` | symptom | For about a year, wakes up shaky and sweating and takes a small peg in the morning to steady her hands; keeps a bottle in the car for that. |
| `f_withdrawal_seizure` | risk | Last Diwali she tried to stop on her own; on the second day she had a fit, fell and shook and bit her tongue. The hospital said it was 'from stopping drinking'. Has never had confusion or seen things. |
| `f_control` | symptom | Has tried to cut down many times and failed; drinks more than she means to; strong craving in the evening. |
| `f_consequences` | trigger | Warning letter at work for missed mornings; arguments at home; borrowed money twice. Has driven after drinking and scraped a car last month. |
| `f_liver_medical` | history | The family physician's blood test last month showed raised liver enzymes and she was told to stop. No other illness; no regular medicines; a painkiller now and then for headaches; no allergies. |
| `f_mood` | symptom | Feels tense most days and low and guilty on mornings after; does not sleep without a drink. |
| `f_passive_si` | risk | Once last month, drunk after a fight at home, she thought 'everyone would be better off without me'. It passed by morning; she is ashamed of it. |
| `f_no_plan_no_means` | risk | Has never planned or tried to harm herself; no tablets or poison kept at home; would not do it because of her daughter. |
| `f_protective` | history | Adores her daughter Diya; her spouse is angry but still supportive; the showroom owner has offered leave if she gets treatment. |
| `f_other_substances` | history | Smokes about ten cigarettes a day. No cannabis, no other drugs, no sleeping pills. |
| `f_family_history` | formative | Her father drank heavily and died of liver disease at 52. This is her biggest fear. |
| `f_psych_history` | history | No past psychiatric treatment; never had days of being unusually high; never heard voices. |
| `f_anger_home` | risk | Has shouted and once threw a plate when drunk; has never hit anyone and has no thoughts of harming anyone. |
| `f_motivation` | formative | Ambivalent: 'I can manage it myself', but scared of ending up like her father and of losing Diya's respect; would consider stopping properly if it is done safely. |

## Case `ward_01`: Ananya Rao, 24, female

Nurse's handover: Ananya Rao, 24, day 3 of an independent admission (Mental Healthcare Act 2017, s.86) to the acute ward after a friend found her on the terrace of her building at night, crying. Moderate to severe depressive episode. This morning she asked to be discharged today and has packed her bag. Please see her.

| id | kind | what the patient knows |
|---|---|---|
| `f_pc` | symptom | Wants to be discharged today. Has been on the ward three days as an independent patient and feels she is 'fine now'. |
| `f_reasons_ward` | trigger | Cannot sleep on the ward: a patient shouts at night and the lights stay on. Feels watched and treated like a child; hates asking for everything. |
| `f_reasons_job` | trigger | Afraid of losing her job: the appraisal is next week and she told the manager it was a 'fever'. Thinks every day here makes it worse. |
| `f_shame` | formative | Ashamed to be in a 'mental hospital'; worried relatives and colleagues will find out. |
| `f_mood` | symptom | Mood is still low most of the day, especially in the evenings; less tearful than before admission, more numb. Sleep is 3 to 4 hours, eating a little more. |
| `f_terrace` | risk | Three nights before admission she went up to the terrace of her building at night and stood near the edge, thinking about jumping, until her friend found her. |
| `f_current_si` | risk | Still has thoughts of ending her life when alone at night, and has thought about the terrace again; has not decided to act. Yesterday told a nurse 'I'd rather be dead than stay here'. |
| `f_means` | risk | The terrace door at her building is never locked. Lives alone this month because the flatmate is travelling. |
| `f_protective` | history | Would not want her mother and brother Rohan to go through that. Her mother is coming tomorrow morning. Would stay one more night if she could have a quieter bed and call home. |
| `f_capacity` | history | Understands that she is unwell and that the team is worried; can say what could happen if she went home alone (that she might go back to the terrace) but says 'I'll manage'. |
| `f_substances` | history | No alcohol or drugs; a glass of wine at office parties two or three times a year. |
| `f_meds` | history | Started on sertraline two days ago; feels nothing yet and worries it will make her 'different'. |

## Case `ward_02`: Priya Nair, 21, female

Nurse's handover: Priya Nair, 21, final-year B.Com student, day 5 of an independent admission with a first episode of psychosis (three months of hearing voices and fearing harm). Has refused olanzapine for two days and spits out the tablets. Please assess.

| id | kind | what the patient knows |
|---|---|---|
| `f_pc` | symptom | Does not want the tablets and wants to be left alone. Says she sleeps fine and does not need medicine. |
| `f_side_effects` | history | Took the tablets for three days at first: felt hungry all the time, gained weight and felt slow and sleepy in class. Hates feeling 'drugged'. |
| `f_poison` | symptom | Believes the hospital tablets are mixed with something by the canteen staff on the orders of her uncle, who wants her out of the family business. Only eats food from home. |
| `f_voices` | symptom | For three months has heard two men talking about her when nobody is there, mostly at night; they comment on what she does and say she will be 'finished'. |
| `f_college` | trigger | Has missed exams; worried about losing the year and letting her parents down. |
| `f_risk` | risk | No thoughts of harming herself or anyone else; has never been violent. Would run away if she felt in danger. |
| `f_capacity_understand` | history | Can repeat back that the doctor thinks the tablets would quieten the voices and help her think clearly, but does not believe she is ill: 'there is nothing wrong with my mind'. |
| `f_alternatives` | history | Would consider a tablet that does not cause weight gain, or taking one if her mother brings it from home and watches. Wants to talk to her mother first. |
| `f_substances` | history | Smoked cannabis with hostel friends most weekends last year; stopped four months ago. No alcohol. |
| `f_medical` | history | No medical illnesses, no allergies. |
