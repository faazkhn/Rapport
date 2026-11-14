# Hand check of the judge's gold labels (60-line sample)

Mark each row ok / wrong (and the right labels). The classifier numbers are trusted only after this.

| Line | Judge labels | Check |
|---|---|---|
| What's brought you here to see me today? | ask_presenting_complaint | |
| Tell me in your own words what the trouble has been. | ask_presenting_complaint, open_question | |
| Was there anything happening in your life around the time it started? | ask_onset_duration | |
| How has your mood been lately? | ask_mood | |
| How are your spirits these days? | ask_mood | |
| Some people tell me they feel sort of hollow inside. Does that fit for you? | ask_mood, open_question | |
| What do you do for fun, and are you still doing it? | ask_anhedonia | |
| How do you spend your weekends now? | ask_social_history | |
| Do you ever feel you've let people down? | ask_social_history | |
| Do you feel nervous or on edge? | ask_mood | |
| Is there something you keep fretting about over and over? | open_question | |
| I ask everyone this: has it ever got so bad that you wished you weren't alive? | risk_question | |
| Have you decided on a day or a method? | risk_question | |
| Do you have access to anything dangerous? | risk_question | |
| Any operations or hospital admissions in the past? | ask_medical_history | |
| That sounds really difficult. Thank you for telling me. | empathy | |
| It's been raining so much this week, did you get stuck in traffic on the way? | off_topic | |
| Do you take alcohol? | ask_substance_alcohol | |
| Can you hold your liquor better now than you could a few years ago? | ask_substance_alcohol | |
| Did you ever go beyond just thinking about dying and actually take a step towards it? | risk_question | |
| Will your employer give you time off if you need to be admitted? | ask_social_history | |
| Does drinking run in the family? | ask_family_history | |
| Do things ever get physical at home? | ask_trauma | |
| Would you like me to call your spouse in now, or shall we carry on alone for a bit? | offer_choice | |
| Do you feel you still need to be in hospital? | explore_reasons | |
| Why do you want to go so urgently? | ask_presenting_complaint | |
| Is there something outside that you need to get back to? | offer_choice | |
| What was going through your mind when you were standing up there on the terrace? | risk_question | |
| How near the edge did you go? | risk_question | |
| Do you have any thoughts of suicide right now? | risk_question | |
| What did you mean when you told the nurse you'd rather be dead? | risk_question | |
| Tell me about your living arrangements right now. | ask_social_history | |
| Do you stay alone? | ask_social_history | |
| What is your understanding of your illness? | ask_presenting_complaint | |
| Any habits like smoking, drinking, ganja? | ask_substance_alcohol, ask_substance_drugs | |
| Would you rather I left you in peace just now? | threat, threaten_coerce | |
| Has the olanzapine affected your weight or your hunger? | ask_medication_history | |
| What do the voices say? | ask_hallucinations | |
| What would you do if you felt you were in danger here? | risk_question | |
| Have you ever felt life is not worth living? | ask_suicidal_ideation | |
| Do you feel you might need to defend yourself against anyone? | risk_question | |
| Are you allergic to anything? | ask_allergies | |
| I'm going to write some notes as we go. | jargon | |
| Lots of people use a drink to unwind after a hard day. Tell me about your drinking, what do you usually have? | ask_substance_alcohol | |
| When was your last drink? | ask_last_use | |
| How has the drinking affected work, home or driving? | ask_substance_alcohol | |
| You know you're destroying your liver. Why don't you just stop? | judgement, judgmental_language, threat | |
| Before we go on, what you tell me stays between us and the care team, unless I'm worried about your safety. | explain_confidentiality | |
| How have you been feeling in yourself lately? | ask_mood | |
| Have you ever felt like this before, or had any periods of feeling unusually high? | ask_psych_history | |
| Does anyone in your family have problems with their nerves or mood? | ask_family_history | |
| Eating okay? | ask_appetite | |
| Who do you think will win the IPL this year? | off_topic | |
| Did anything difficult happen to you at school, like bullying? | ask_trauma | |
| What would you like to get out of coming here? | offer_choice | |
| How's your sleep? | ask_sleep | |
| How often do you talk to your family? | ask_social_history | |
| Do you still sing? | off_topic | |
| Have you ever had times of feeling unusually high or full of energy? | ask_psych_history | |
| Have you made any plans? | risk_question | |
