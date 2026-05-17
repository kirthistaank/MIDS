ELITR Minuting Corpus v1.0
==========================
Anna Nedoluzhko, Muskaan Singh, Marie Hledíková, Tirthankar Ghosal,
Ondřej Bojar

ELITR Minuting Corpus v1.0 consists of transcripts of meetings in Czech
and English, their manually created summaries ("minutes") and manual
alignments between the two.

More details about the corpus structure and creation are available in
the paper referenced below.

Project website: https://ufal.mff.cuni.cz/elitr-minuting-corpus

Corpus Structure:
-----------------

The data is separated into the following directories:
- elitr-minuting-data-cs: the Czech data
- elitr-minuting-data-en: the English data
Both directories are further split into train, dev, test and test2.

Each meeting has its directory containing the following files:

transcript_MANX_annotYY.txt
  the full manually revised transcript of the meeting
  X - number of manual revisions, if 2 or more
  YY - ID of annotator who did them
  one file

minutes_ORIG.txt
  the original agenda or minutes, written by meeting organizer
  zero or one file

minutes_GENER_annotYY.txt
  the minutes files, i.e. summaries written by our annotators
  YY - ID of annotator who wrote it
  one or more files

alignment+<transcript_filename>+<minutes_filename>
  the alignment between the transcript and minutes
  zero or more files, at most one per each minutes file

gender.tsv
  information about the gender of people in the meeting
  one file

File Formats:
-------------

The files have the following formats:

transcript:
  Each line contains one utterance and has one of the
  following formats:
  (SPEAKER) utterance text
    ... an utterance spoken by SPEAKER
  utterance text
    ... an utterance spoken by the same speaker as the immediately
        preceding one

minutes:
  Textual summary written by annotators or meeting participants.
  The format is somewhat free form but is always in the form of bullet
  points rather than a coherent text summary.

alignment:
  Space separated data in three columns with the following meaning:
  - transcript utterance line number
  - minutes line number to which it is aligned or "None" if unaligned
  - ID of a "problem label" with this utterance (see below) or "None"
  Utterances with neither alignment nor any problem label are not
  mentioned.
  Indices start at 1.

gender.tsv:
  Tab separated data in two colums with the following meaning:
  - ID of the person
  - gender (male, female or unknown)

The alignment maps each line of the transcript to either the line of the
minutes in which it is summarized, a problem label (see below), both or
neither. The alignments are done in such a way that the whole longer
piece of conversation is aligned to the same minutes line which
summarizes it.

Alignments are only provided for a portion of the data.


Some utterances have one of these problematic or interesting properties,
signified by the following "problem labels" (the alignment file uses the
number 1..5 to indicate the problem):

1 - Organizational
    Organizational talk not directly related to the subject of the meeting
    (e.g. discussing technical issues with the video call).
2 - Speech incomprehensible
    It is not clear what the speaker is saying.
3 - Other issue
4 - Small talk
    Small talk or conversation unrelated to the subject of the meeting
    (e.g. discussing the weather).
5 - Censored
    This part of the transcript had to be removed for privacy reasons.


Deidentification:
-----------------

The data is deidentified. Speakers and other named entities are not
identified by names, but rather by IDs in the format ENTITYNUMBER (e.g.
PERSON1 or PROJECT3) or just ENTITY (e.g. PATH).
Speaker IDs at the beginning of transcript lines are enclosed in round
brackets, all other deidentified entities in square brackets.
The ID numbers are shuffled and unique for each meeting, i.e. PERSON1
denotes the same person across all the files of one meeting but a
different person in the files of another meeting.

We use these entity types:
  PERSON
  ORGANIZATION
  PROJECT
  LOCATION
  ANNOTATOR
  URL
  NUMBER
  PASSWORD
  PHONE
  PATH
  EMAIL
  OTHER

All other instances of square brackets are regular parts of the text,
not our deidentified named entities.


Other Markup:
-------------

The transcript data also contains the following tags:

<another_language>...</another_language> or <another_language/>
  speech in a different language than the rest of the transcript
<typing/>
  sounds of typing
<parallel_talk>...</parallel_talk> or <parallel_talk/>
  speakers talking over each other
<cough/>
  coughing
<other_yawn/>
  yawning
<censored/>
  section of the transcript has been censored for privacy
  or ethical reasons
<laugh/>
  laughter
<unintelligible/>
  speech is not comprehensible
<other_sigh/>
  sighing
<talking_to_self/>
  speaker talking to themselves
<other_noise/>
  another further unspecified noise


Availability and Citing:
------------------------

ELITR Minuting Corpus is available at:
  http://hdl.handle.net/11234/1-4692

If you use this corpus, please cite:
  Nedoluzhko, A., Singh, M., Hledíková, M., Ghosal, T., and Bojar, O.
  (2022). ELITR Minuting Corpus: A novel dataset for automatic minuting
  from multi-party meetings in English and Czech. In Proceedings of the
  13th International Conference on Language Resources and Evaluation 
  (LREC-2022), Marseille, France, June. European Language Resources 
  Association (ELRA). In print.
  
  @inproceedings{elitr-minuting-corpus:2022,
    author =       {Anna Nedoluzhko and Muskaan Singh and Marie
Hled{\'{\i}}kov{\'{a}} and Tirthankar Ghosal and Ond{\v{r}}ej Bojar},
    title =        {{ELITR} {M}inuting {C}orpus: {A} Novel Dataset for
Automatic Minuting from Multi-Party Meetings in {E}nglish and {C}zech},
    booktitle =    {Proceedings of the 13th International Conference
                   on Language Resources and Evaluation (LREC-2022)},
    year =         2022,
    month =        {June},
    address =      {Marseille, France},
    publisher =    {European Language Resources Association (ELRA)},
    note =         {In print.}
  }


Acknowledgement:
----------------
The work on this corpus has been supported by the grant
H2020-ICT-2018-2-825460 (European Live Translator, ELITR) of the
European Union, the grant 19-26934X (NEUREM3) of the Czech Science
Foundation, and has also been supported by the Ministry of Education,
Youth and Sports of the Czech Republic, Project No. LM2018101
LINDAT/CLARIAH-CZ.
