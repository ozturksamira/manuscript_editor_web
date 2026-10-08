const WORD_RE = /\b[A-Za-z](?:[A-Za-z'’-]*[A-Za-z])?\b/g;
const SENTENCE_RE = /[^.!?\n]+(?:[.!?]+|$)/g;
const AUXILIARY_WORDS = new Set(["am","is","are","was","were","be","being","been","have","has","had","having","do","does","did","can","could","may","might","must","shall","should","will","would","ought","need","dare","used"]);
const PRONOUNS = new Set(["i","me","my","myself","you","your","yourself","yours","he","him","his","himself","she","her","hers","herself","it","its","itself","we","us","our","ourselves","they","them","their","theirs","themselves","who","whom","whose","which","that","this","these","those"]);
const PREPOSITIONS = new Set(["about","above","across","after","against","along","among","around","at","before","behind","below","beneath","beside","between","beyond","by","down","during","except","for","from","in","inside","into","like","near","of","off","on","onto","out","outside","over","past","through","throughout","to","toward","under","underneath","until","up","upon","with","within","without"]);
const CONJUNCTIONS = new Set(["and","but","or","nor","for","yet","so","although","because","since","unless","until","while","whereas"]);
const CONTRACTION_STOP_WORDS = new Set(["i'm","i’ve","i'll","i’d","you're","you’ve","you'll","you’d","he's","he’ll","he’d","she's","she’ll","she’d","it's","it’ll","it’d","we're","we’ve","we'll","we’d","they're","they’ve","they'll","they’d","who's","who’ll","who’d","that's","that’ll","that’d","can't","couldn't","won't","wouldn't","shouldn't","shan't","isn't","aren't","wasn't","weren't","ain't","haven't","hasn't","hadn't","don't","doesn't","didn't","could've","couldn’t","would've","wouldn’t","should've","shouldn’t","might've","mightn’t","must've","mustn’t","needn't","daren't","oughtn't","usedn't","cannot"]);
const COMMON_GRAMMAR_WORDS = new Set([
  "a","an","the","and","but","or","nor","so","yet","as","if","then","than",
  "not","no","yes","back","away","very","just","also","too","still","already",
  "again","ever","never","now","here","there","when","where","why","how",
  "what","who","whom","which","this","that","these","those","some","any",
  "all","each","every","both","either","neither","more","most","less","least",
  "much","many","few","little","own","same","such"
]);
const STOP_WORDS = new Set([...PRONOUNS, ...PREPOSITIONS, ...CONJUNCTIONS, ...AUXILIARY_WORDS, ...CONTRACTION_STOP_WORDS, ...COMMON_GRAMMAR_WORDS]);
const COMMON_CAPITALIZED_WORDS = new Set([
  "river","house","chapter","book","room","door","road","street","city","town","village",
  "country","world","earth","sun","moon","sky","sea","ocean","mountain","hill","forest",
  "garden","church","school","university","hospital","office","hotel","king","queen",
  "prince","princess","captain","general","president","mother","father","brother","sister",
  "friend","stranger","man","woman","child","children","boy","girl","doctor","teacher",
  "writer","author","soldier","officer","police","letter","story","page","scene","day",
  "night","morning","evening","summer","winter","spring","autumn","monday","tuesday",
  "wednesday","thursday","friday","saturday","sunday","january","february","march","april",
  "may","june","july","august","september","october","november","december"
]);
const COMMON_PROPER_NAMES = new Set([
  "john","mary","james","robert","michael","william","david","richard","thomas","charles",
  "joseph","daniel","matthew","anthony","mark","paul","steven","andrew","joshua","george",
  "kevin","brian","edward","ronald","timothy","jason","jeffrey","ryan","jacob","gary",
  "nicholas","eric","jonathan","stephen","larry","justin","scott","brandon","benjamin",
  "samuel","gregory","alexander","patrick","frank","raymond","jack","dennis","jerry",
  "tyler","aaron","henry","adam","douglas","nathan","peter","zachary","kyle","walter",
  "harold","jeremy","ethan","carl","keith","roger","gerald","christian","terry","sean",
  "arthur","austin","noah","jesse","albert","bryan","bruce","jordan","dylan","alan",
  "ralph","gabriel","roy","wayne","eugene","logan","randy","louis","russell","vincent",
  "philip","bobby","johnny","bradley","mason","lucas","patricia","jennifer","linda",
  "elizabeth","barbara","susan","jessica","sarah","karen","nancy","lisa","margaret",
  "betty","sandra","ashley","kimberly","donna","emily","michelle","carol","amanda",
  "melissa","deborah","stephanie","rebecca","laura","sharon","cynthia","kathleen","amy",
  "shirley","anna","angela","ruth","brenda","pamela","nicole","katherine","samantha",
  "christine","emma","catherine","debra","virginia","rachel","carolyn","janet"
]);
const EVENT_VERBS = new Set(["arrive","arrived","attack","attacked","avoid","avoided","break","broke","burst","build","built","call","called","catch","caught","change","changed","chase","chased","choose","chose","close","closed","crash","crashed","cry","cried","cut","cutting","die","died","discover","discovered","drag","dragged","drive","drove","escape","escaped","enter","entered","explode","exploded","fall","fell","fight","fought","find","found","flee","fled","grab","grabbed","hit","hold","held","jump","jumped","kick","kicked","kill","killed","leave","left","lose","lost","open","opened","pull","pulled","push","pushed","reach","reached","raise","raised","react","reacted","run","ran","rush","rushed","scream","screamed","search","searched","see","saw","send","sent","shake","shook","shoot","shot","shout","shouted","slam","slammed","slip","slipped","smash","smashed","sprint","sprinted","stand","stood","start","started","stop","stopped","strike","struck","survive","survived","take","took","throw","threw","turn","turned","wake","woke","walk","walked","warn","warned","watch","watched","whisper","whispered","write","wrote"]);
const DESCRIPTION_RE = /\b(?:very|quite|rather|really|extremely|beautifully|slowly|quickly|carefully|suddenly|silently|quietly|loudly|softly|deeply|[A-Za-z-]*(?:ly|ful|ous|ive|less|ish|ical))\b/gi;
const IRREGULAR_PARTICIPLES = new Set(["arisen","awoken","been","begun","bitten","blown","born","bought","bound","broken","brought","built","burnt","caught","chosen","come","cost","cut","dealt","done","drawn","driven","eaten","fallen","felt","fought","found","flown","forgiven","forgotten","frozen","given","gone","grown","heard","held","hidden","hit","hurt","kept","known","laid","led","left","lent","let","lost","made","meant","met","paid","put","read","ridden","run","said","seen","sent","set","shaken","shown","shut","sung","sold","spent","spoken","stood","stolen","stuck","struck","sworn","swum","taken","taught","torn","told","thought","thrown","understood","woken","won","worn","written"]);

function wordsIn(text) {
  WORD_RE.lastIndex = 0;
  return [...String(text || "").matchAll(WORD_RE)].map((m) => m[0].toLowerCase().replace(/’/g, "'").replace(/^'+|'+$/g, ""));
}

function countWords(text) {
  return wordsIn(text).length;
}

function properNounCandidates(value) {
  const text = String(value || "");
  const stats = new Map();
  let sentenceHasWord = false;
  let cursor = 0;
  let previousWord = "";
  WORD_RE.lastIndex = 0;

  for (const match of text.matchAll(WORD_RE)) {
    const between = text.slice(cursor, match.index);
    if (/[.!?\n]/.test(between)) sentenceHasWord = false;

    const raw = match[0];
    const word = raw.toLowerCase().replace(/’/g, "'").replace(/^'+|'+$/g, "");
    if (word.length >= 2 && !STOP_WORDS.has(word)) {
      const row = stats.get(word) || {
        capitalized: 0,
        lowercase: 0,
        nonInitial: 0,
        sentenceInitial: 0,
      };
      if (/^[A-Z]/.test(raw)) {
        row.capitalized += 1;
        if (sentenceHasWord) row.nonInitial += 1;
        else row.sentenceInitial += 1;
      } else {
        row.lowercase += 1;
      }
      stats.set(word, row);
    }

    sentenceHasWord = true;
    previousWord = word;
    cursor = match.index + raw.length;
  }

  const candidates = new Set();
  for (const [word, row] of stats) {
    if (row.lowercase > 0 || COMMON_CAPITALIZED_WORDS.has(word)) continue;
    if (row.nonInitial > 0 || (row.sentenceInitial >= 2 && (COMMON_PROPER_NAMES.has(word) || row.capitalized >= 3))) {
      candidates.add(word);
    }
  }
  return candidates;
}
function sentenceSpans(value) {
  SENTENCE_RE.lastIndex = 0;
  const output = [];
  for (const match of String(value || "").matchAll(SENTENCE_RE)) {
    const raw = match[0];
    const snippet = raw.trim();
    if (!snippet) continue;
    const leading = raw.length - raw.trimStart().length;
    output.push({ start: match.index + leading, end: match.index + raw.trimEnd().length, sentence: snippet });
  }
  return output;
}

function profile(snippet) {
  const words = wordsIn(snippet);
  const contentWords = words.filter((word) => !STOP_WORDS.has(word));
  const eventCount = words.filter((word) => EVENT_VERBS.has(word)).length;
  DESCRIPTION_RE.lastIndex = 0;
  const descriptionCount = [...snippet.matchAll(DESCRIPTION_RE)].length;
  return {
    word_count: words.length,
    content_word_count: contentWords.length,
    content_variety: contentWords.length ? new Set(contentWords).size / contentWords.length : 1,
    event_count: eventCount,
    event_density: words.length ? eventCount / words.length : 0,
    description_count: descriptionCount,
    description_density: words.length ? descriptionCount / words.length : 0,
    dialogue: /["“”]/.test(snippet) ? 1 : 0,
    questions: (snippet.match(/\?/g) || []).length,
    exclamations: (snippet.match(/!/g) || []).length,
  };
}

function isParticiple(word) {
  const value = String(word || "").toLowerCase().replace(/^'+|'+$/g, "");
  return IRREGULAR_PARTICIPLES.has(value) || value.endsWith("ed") || value.endsWith("en") || value.endsWith("wn") || value.endsWith("t");
}

const PASSIVE_AUX_RE = /\b(?:am|is|are|was|were|be|been|being)\b(?:\s+(?:not|never|already|still|just|quickly|slowly|suddenly|clearly|completely|immediately|possibly|probably|often|usually|nearly|almost|finally)){0,3}\s+(?<participle>[A-Za-z][A-Za-z'’-]*)\b/gi;
const GET_PASSIVE_RE = /\b(?:get|gets|got|getting|gotten)\b(?:\s+(?:not|never|already|still|just|quickly|slowly|suddenly)){0,2}\s+(?<participle>[A-Za-z][A-Za-z'’-]*)\b/gi;

function passiveFindings(snippet, start) {
  const findings = [];
  const seen = new Set();
  for (const regex of [PASSIVE_AUX_RE, GET_PASSIVE_RE]) {
    regex.lastIndex = 0;
    for (const match of snippet.matchAll(regex)) {
      const participle = match.groups?.participle || "";
      if (!isParticiple(participle)) continue;
      const key = match.index + ":" + match[0];
      if (seen.has(key)) continue;
      seen.add(key);
      const trailing = snippet.slice(match.index + match[0].length, match.index + match[0].length + 90);
      const hasAgent = /\bby\s+(?:the|a|an)?\s*[A-Za-z][A-Za-z'’-]*\b/i.test(trailing);
      findings.push({
        sentence: snippet.slice(0, 500),
        start,
        end: start + snippet.length,
        reason: hasAgent ? "High-confidence passive voice — explicit agent" : "Possible passive voice — action recipient is in subject position",
        confidence: hasAgent ? "high" : "medium",
      });
    }
  }
  return findings;
}

export function analyseText(value) {
  const text = String(value || "");
  if (!text.trim()) return { word_count: 0, words: [], passive: [], pacing: [], flagged_count: 0 };
  const spans = sentenceSpans(text);
  const properNouns = properNounCandidates(text);
  const counts = new Map();
  WORD_RE.lastIndex = 0;
  for (const match of text.matchAll(WORD_RE)) {
    const word = match[0].toLowerCase().replace(/’/g, "'").replace(/^'+|'+$/g, "");
    if (word.length < 2 || STOP_WORDS.has(word) || properNouns.has(word)) continue;
    counts.set(word, (counts.get(word) || 0) + 1);
  }
  const frequent = [...counts.entries()]
    .filter(([, count]) => count > 3)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, 100);
  const frequentSet = new Set(frequent.map(([word]) => word));
  const contexts = {};
  for (const item of spans) {
    if (Object.keys(contexts).length >= frequentSet.size) break;
    for (const word of wordsIn(item.sentence)) {
      if (!frequentSet.has(word)) continue;
      contexts[word] ??= [];
      if (contexts[word].length < 3 && !contexts[word].includes(item.sentence.slice(0, 300))) {
        contexts[word].push(item.sentence.slice(0, 300));
      }
    }
  }
  const profiles = [];
  const passive = [];
  for (const item of spans) {
    const row = { ...profile(item.sentence), ...item };
    profiles.push(row);
    passive.push(...passiveFindings(item.sentence, item.start));
    if (passive.length >= 120) break;
  }
  const pacing = [];
  const windowText = (window) => window.map((item) => item.sentence.trim()).join(" ");
  for (let i = 0; i <= profiles.length - 3; i++) {
    const window = profiles.slice(i, i + 3);
    const totalWords = window.reduce((sum, item) => sum + item.word_count, 0);
    const avgWords = totalWords / 3;
    const eventTotal = window.reduce((sum, item) => sum + item.event_count, 0);
    const eventDensity = totalWords ? eventTotal / totalWords : 0;
    const shortSentences = window.filter((item) => item.word_count <= 15).length;
    if (shortSentences >= 2 && eventTotal >= 2 && avgWords <= 17 && eventDensity >= 0.055) {
      pacing.push({ sentence: windowText(window).slice(0, 650), start: window[0].start, end: window[2].end, reason: "Too fast — possible event compression", word_count: totalWords, confidence: "medium" });
    }
    if (pacing.length >= 80) break;
  }
  if (pacing.length < 80) {
    for (let i = 0; i <= profiles.length - 4; i++) {
      const window = profiles.slice(i, i + 4);
      const totalWords = window.reduce((sum, item) => sum + item.word_count, 0);
      const avgWords = totalWords / 4;
      const eventTotal = window.reduce((sum, item) => sum + item.event_count, 0);
      const eventDensity = totalWords ? eventTotal / totalWords : 0;
      const descriptionDensity = totalWords ? window.reduce((sum, item) => sum + item.description_count, 0) / totalWords : 0;
      const dialogueRate = window.reduce((sum, item) => sum + item.dialogue, 0) / 4;
      const variety = window.reduce((sum, item) => sum + item.content_variety, 0) / 4;
      const dragSignal = descriptionDensity >= 0.06 || dialogueRate >= 0.5 || variety <= 0.62;
      if (avgWords >= 12 && eventTotal <= 2 && eventDensity <= 0.04 && dragSignal) {
        pacing.push({ sentence: windowText(window).slice(0, 700), start: window[0].start, end: window[3].end, reason: "Too slow — possible dragging passage", word_count: totalWords, confidence: "medium" });
      }
      if (pacing.length >= 80) break;
    }
  }
  if (pacing.length < 100 && profiles.length >= 8) {
    for (let i = 0; i <= profiles.length - 8; i++) {
      const window = profiles.slice(i, i + 8);
      const lengths = window.map((item) => item.word_count);
      const events = window.map((item) => item.event_count);
      const meanLen = lengths.reduce((a, b) => a + b, 0) / 8;
      const variance = lengths.reduce((sum, x) => sum + (x - meanLen) ** 2, 0) / 8;
      const stdev = Math.sqrt(variance);
      const eventRange = Math.max(...events) - Math.min(...events);
      const rhythmScores = window.map((item) => (item.word_count / 8) + item.event_count * 2 + item.dialogue * 0.6 + (item.questions + item.exclamations) * 0.5);
      const rhythmMean = rhythmScores.reduce((a, b) => a + b, 0) / 8;
      const rhythmVariance = rhythmScores.reduce((sum, score) => sum + (score - rhythmMean) ** 2, 0) / 8;
      const rhythmStdev = Math.sqrt(rhythmVariance);
      if (meanLen >= 5 && meanLen <= 28 && stdev <= 4.5 && eventRange <= 1 && rhythmStdev <= 1.7) {
        pacing.push({ sentence: windowText(window).slice(0, 750), start: window[0].start, end: window[7].end, reason: "Flat dynamics — sustained single-gear rhythm", word_count: lengths.reduce((a, b) => a + b, 0), confidence: "medium" });
      }
      if (pacing.length >= 100) break;
    }
  }
  const deduped = [];
  const lastEndByReason = new Map();
  for (const item of pacing) {
    const previous = lastEndByReason.get(item.reason) ?? -1;
    if (item.start <= previous) continue;
    deduped.push(item);
    lastEndByReason.set(item.reason, item.end);
  }
  return {
    word_count: wordsIn(text).length,
    words: frequent.map(([word, count]) => ({ word, count, contexts: contexts[word] || [] })),
    passive: passive.slice(0, 120),
    pacing: deduped.slice(0, 100),
    flagged_count: frequent.length + Math.min(passive.length, 120) + Math.min(deduped.length, 100),
  };
}

export { countWords };