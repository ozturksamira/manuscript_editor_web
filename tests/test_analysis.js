import assert from "node:assert/strict";
import { analyseText, countWords } from "../public/analysis.js";

const repeated = analyseText("The lantern burned. The lantern swung. The lantern shook. The lantern glowed.");
assert.equal(repeated.words.find((item) => item.word === "lantern")?.count, 4);
assert.equal(repeated.word_count, 16);

const passive = analyseText("The ball was caught by the dog.");
assert.equal(passive.passive.length > 0, true);

const fast = analyseText("He ran. He jumped. He shouted. He struck the door.");
assert.equal(fast.pacing.some((item) => item.reason.startsWith("Too fast")), true);

const slow = analyseText(
  "The hallway was very quiet and extremely narrow, with beautiful old portraits on every wall. " +
  "The wallpaper was faded and the carpet was worn, and the air was unusually still. " +
  "She looked at the pictures and thought about their colours for a long time. " +
  "The room remained silent as she carefully studied each frame."
);
assert.equal(slow.pacing.some((item) => item.reason.startsWith("Too slow")), true);

const flat = analyseText(
  "She walked across the room. She walked toward the door. She walked beside the table. " +
  "She walked past the window. She walked around the chair. She walked toward the hall. " +
  "She walked through the doorway. She walked into the corridor."
);
assert.equal(flat.pacing.some((item) => item.reason.startsWith("Flat dynamics")), true);

const stopTest = analyseText("I am a writer and you are here. I am here because I write.");
assert.equal(stopTest.words.some((item) => ["i", "am", "and", "you", "are", "because"].includes(item.word)), false);
assert.equal(countWords("I am a writer and you are here."), 8);

console.log("Cloudflare analysis tests passed.");
