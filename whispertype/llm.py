"""Local SLM post-processor, spoken code transformer, and dialect style transformers."""

import json
import re
import urllib.request
import urllib.error
from typing import Dict, Optional


SPOKEN_CODE_RULES = [
    # Variable assignments & declarations
    (re.compile(r'\b(?i:let|const|var)\s+([a-zA-Z0-9_]+)\s+(?:equal to|equals|=)\s+', re.IGNORECASE), r'\1 = '),
    # Increments / Decrements
    (re.compile(r'\b([a-zA-Z0-9_]+)\s+plus\s+plus\b', re.IGNORECASE), r'\1++'),
    (re.compile(r'\b([a-zA-Z0-9_]+)\s+minus\s+minus\b', re.IGNORECASE), r'\1--'),
    (re.compile(r'\b([a-zA-Z0-9_]+)\s+plus\s+equals\s+([a-zA-Z0-9_]+)\b', re.IGNORECASE), r'\1 += \2'),
    (re.compile(r'\b([a-zA-Z0-9_]+)\s+minus\s+equals\s+([a-zA-Z0-9_]+)\b', re.IGNORECASE), r'\1 -= \2'),
    # Comparisons & equality
    (re.compile(r'\s*\b(?i:triple equals)\b\s*', re.IGNORECASE), r' === '),
    (re.compile(r'\s*\b(?i:double equals|equals equals)\b\s*', re.IGNORECASE), r' == '),
    (re.compile(r'\s*\b(?i:not equals|does not equal|not equal to)\b\s*', re.IGNORECASE), r' != '),
    (re.compile(r'\s*\b(?i:greater than or equal to)\b\s*', re.IGNORECASE), r' >= '),
    (re.compile(r'\s*\b(?i:less than or equal to)\b\s*', re.IGNORECASE), r' <= '),
    # Arrows & scope resolution
    (re.compile(r'\s*\b(?i:fat arrow|hash rocket)\b\s*', re.IGNORECASE), r' => '),
    (re.compile(r'\s*\b(?i:thin arrow|arrow operator|arrow)\b\s*', re.IGNORECASE), r' -> '),
    (re.compile(r'\s*\b(?i:colon colon|double colon)\b\s*', re.IGNORECASE), r'::'),
    # Brackets & Delimiters
    (re.compile(r'\s*\b(?i:open paren|left paren)\b\s*', re.IGNORECASE), r'('),
    (re.compile(r'\s*\b(?i:close paren|right paren)\b\s*', re.IGNORECASE), r')'),
    (re.compile(r'\s*\b(?i:open brace|open curly|left brace)\b\s*', re.IGNORECASE), r'{ '),
    (re.compile(r'\s*\b(?i:close brace|close curly|right brace)\b\s*', re.IGNORECASE), r' }'),
    (re.compile(r'\s*\b(?i:open bracket|left bracket)\b\s*', re.IGNORECASE), r'['),
    (re.compile(r'\s*\b(?i:close bracket|right bracket)\b\s*', re.IGNORECASE), r']'),
    (re.compile(r'\s*\b(?i:semicolon)\b\s*', re.IGNORECASE), r';'),
    # Conditionals
    (re.compile(r'\b(?i:if)\s+(.+?)\s+(?:then|colon)\b', re.IGNORECASE), r'if \1:'),
    # Returns
    (re.compile(r'\b(?i:return)\s+(true|false|null|nil|none)\b', re.IGNORECASE), r'return \1;'),
]


GANGSTER_RULES = [
    # Multi-word idioms & phrases
    (re.compile(r'\b(?i:you know what I mean|you know what I\'?m sayin\'?g?)\b'), "nah'mean"),
    (re.compile(r'\b(?i:do you understand|understand\?)\b'), "ya feel me?"),
    (re.compile(r'\b(?i:I understand)\b'), "I feel you"),
    (re.compile(r'\b(?i:you understand)\b'), "ya feel me"),
    (re.compile(r'\b(?i:what is up|what\'s up|what\'s going on)\b'), "what's good"),
    (re.compile(r'\b(?i:going to the)\b'), "headin' to the"),
    (re.compile(r'\b(?i:going to|gonna)\b'), "finna"),
    (re.compile(r'\b(?i:about to)\b'), "boutta"),
    (re.compile(r'\b(?i:trying to)\b'), "tryna"),
    (re.compile(r'\b(?i:want to)\b'), "wanna"),
    (re.compile(r'\b(?i:we need to|need to|have to|got to)\b'), "gotta"),
    (re.compile(r'\b(?i:for real|seriously|honestly)\b'), "fr fr"),
    (re.compile(r'\b(?i:my friends|my crew)\b'), "the squad"),
    (re.compile(r'\b(?i:my friend|brother|friend|buddy|dude)\b'), "my homie"),
    (re.compile(r'\b(?i:you know)\b'), "ya feel me"),
    (re.compile(r'\b(?i:all right|alright)\b'), "aight"),
    (re.compile(r'\b(?i:because|cause)\b'), "cuz"),
    (re.compile(r'\b(?i:with)\b'), "wit'"),
    (re.compile(r'\b(?i:them|those)\b'), "'em"),
    (re.compile(r'\b(?i:is not|are not|am not|have not|has not)\b'), "ain't"),
    (re.compile(r'\b(?i:yes|yeah|yep)\b'), "hell yeah"),
    (re.compile(r'\b(?i:no|nope)\b'), "nah"),
    (re.compile(r'\b(?i:police|cop|cops)\b'), "the feds"),
    (re.compile(r'\b(?i:money|dollars|cash)\b'), "bands"),
    (re.compile(r'\b(?i:car)\b'), "whip"),
    (re.compile(r'\b(?i:house|home)\b'), "crib"),
    (re.compile(r'\b(?i:look at)\b'), "peep"),
    (re.compile(r'\b(?i:give me)\b'), "gimme"),
    (re.compile(r'\b(?i:let me)\b'), "lemme"),
    (re.compile(r'\b(?i:kind of)\b'), "kinda"),
    (re.compile(r'\b(?i:out of)\b'), "outta"),
    (re.compile(r'\b(?i:nothing)\b'), "nothin'"),
    (re.compile(r'\b(?i:something)\b'), "somethin'"),
    (re.compile(r'\b(?i:anything)\b'), "anythin'"),
    (re.compile(r'\b(?i:everything)\b'), "everythin'"),
]

CORPORATE_RULES = [
    (re.compile(r'\b(?i:as I already said|as I told you|like I said)\b'), "per my previous email"),
    (re.compile(r'\b(?i:I don\'?t have time|no time)\b'), "I currently lack the bandwidth"),
    (re.compile(r'\b(?i:we need to talk|talk about this)\b'), "let's touch base and sync offline"),
    (re.compile(r'\b(?i:do your job)\b'), "please ensure alignment on core deliverables"),
    (re.compile(r'\b(?i:that won\'?t work|that is a bad idea|terrible idea)\b'), "I have reservations regarding the scalability of this approach"),
    (re.compile(r'\b(?i:hurry up|as soon as possible|asap)\b'), "at your earliest convenience to expedite our timeline"),
    (re.compile(r'\b(?i:fix this|fix the bug)\b'), "please action this optimization item"),
    (re.compile(r'\b(?i:I don\'?t care)\b'), "I defer to your discretion on this matter"),
    (re.compile(r'\b(?i:think about|consider)\b'), "take a high-level strategic view on"),
    (re.compile(r'\b(?i:problem|issue|bug)\b'), "action item"),
    (re.compile(r'\b(?i:help me|work together)\b'), "synergize with cross-functional partners"),
    (re.compile(r'\b(?i:talk later)\b'), "circle back"),
    (re.compile(r'\b(?i:thanks|thank you)\b'), "best regards"),
]

DISCORD_RULES = [
    (re.compile(r'\b(?i:to be honest)\b'), "tbh"),
    (re.compile(r'\b(?i:not gonna lie|not going to lie)\b'), "ngl"),
    (re.compile(r'\b(?i:for real)\b'), "fr"),
    (re.compile(r'\b(?i:I don\'?t know|I do not know)\b'), "idk"),
    (re.compile(r'\b(?i:as far as I know)\b'), "afaik"),
    (re.compile(r'\b(?i:in my opinion)\b'), "imo"),
    (re.compile(r'\b(?i:by the way)\b'), "btw"),
    (re.compile(r'\b(?i:oh my god)\b'), "omg"),
    (re.compile(r'\b(?i:skull emoji|skull)\b'), "dead"),
    (re.compile(r'\b(?i:crying emoji|crying)\b'), "crying"),
    (re.compile(r'\b(?i:fire emoji|fire)\b'), "fire"),
    (re.compile(r'\b(?i:clown emoji|clown)\b'), "clown"),
    (re.compile(r'\b(?i:stone face|moyai|moai)\b'), "bruh"),
    (re.compile(r'\b(?i:eyes emoji|eyes)\b'), "eyes"),
]

VICTORIAN_RULES = [
    (re.compile(r'\b(?i:hello|hi|hey)\b'), "good morrow"),
    (re.compile(r'\b(?i:goodbye|bye)\b'), "fare thee well"),
    (re.compile(r'\b(?i:please)\b'), "prithee"),
    (re.compile(r'\b(?i:sadly|unfortunately)\b'), "alas"),
    (re.compile(r'\b(?i:really|truly)\b'), "verily"),
    (re.compile(r'\b(?i:I think|maybe|perhaps)\b'), "methinks"),
    (re.compile(r'\b(?i:it is)\b'), "'tis"),
    (re.compile(r'\b(?i:why)\b'), "wherefore"),
    (re.compile(r'\b(?i:has|have)\b'), "hath"),
    (re.compile(r'\b(?i:do not|don\'?t)\b'), "doth not"),
    (re.compile(r'\b(?i:nonsense|bullshit)\b'), "balderdash"),
    (re.compile(r'\b(?i:friend|buddy)\b'), "good compatriot"),
    (re.compile(r'\b(?i:you are)\b'), "thou art"),
    (re.compile(r'\b(?i:you)\b'), "thou"),
    (re.compile(r'\b(?i:your)\b'), "thy"),
]

UWU_FREAK_RULES = [
    # Submissive obedience & flustered verbalizations (pure text, no emojis or symbols)
    (re.compile(r'\b(?i:yes|okay|ok|sure|alright|fine)\b'), "y-yes sir haah"),
    (re.compile(r'\b(?i:please)\b'), "p-pwease be gentle"),
    (re.compile(r'\b(?i:sorry|apologize|apologies|my bad)\b'), "s-sawwy i will be a good giww i pwomise"),
    (re.compile(r'\b(?i:stop|don\'?t)\b'), "yamete unless you want to"),
    (re.compile(r'\b(?i:help me|help)\b'), "u-use me however you want"),
    (re.compile(r'\b(?i:i will|i can|i\'ll)\b'), "i will do anything for you"),
    (re.compile(r'\b(?i:good|great|awesome|amazing)\b'), "so good haah"),
    (re.compile(r'\b(?i:bad|terrible|wrong|error|broken|bug)\b'), "p-punish me"),
    (re.compile(r'\b(?i:do you want|would you like)\b'), "whatever you want master"),
    # Phonetic replacements
    (re.compile(r'\b(?i:what)\b'), 'w-wat'),
    (re.compile(r'\b(?i:you)\b'), 'u'),
    (re.compile(r'\b(?i:your)\b'), 'ur'),
    (re.compile(r'\b(?i:love)\b'), 'wuv'),
    (re.compile(r'\b(?i:the)\b'), 'da'),
    (re.compile(r'\b(?i:this)\b'), 'dis'),
    (re.compile(r'\b(?i:that)\b'), 'dat'),
    (re.compile(r'\b(?i:these)\b'), 'dese'),
    (re.compile(r'\b(?i:those)\b'), 'dose'),
]
UWU_WORDS = UWU_FREAK_RULES

BRAINROT_RULES = [
    (re.compile(r'\b(?i:we are in trouble|we\'?re in trouble|it is over|it\'?s over|we are dead|we\'?re dead)\b'), "we are cooked chat"),
    (re.compile(r'\b(?i:shut up|be quiet|stop talking)\b'), "mewing streak intact don't yap"),
    (re.compile(r'\b(?i:talking too much|talking nonsense|talking)\b'), "yapping"),
    (re.compile(r'\b(?i:talk|speak)\b'), "yap"),
    (re.compile(r'\b(?i:steal|stole|stolen|taking|take)\b'), "fanum tax"),
    (re.compile(r'\b(?i:for real|seriously|honestly)\b'), "on god no cap fr fr"),
    (re.compile(r'\b(?i:great|awesome|attractive|gorgeous)\b'), "level 10 gyatt rizz"),
    (re.compile(r'\b(?i:good|cool|based)\b'), "skibidi sigma"),
    (re.compile(r'\b(?i:bad|terrible|horrible|ugly)\b'), "L rizz"),
    (re.compile(r'\b(?i:error|bug|issue|glitch)\b'), "ohio glitch"),
    (re.compile(r'\b(?i:focus|concentrate)\b'), "lock in"),
    (re.compile(r'\b(?i:friend|bro|dude|man|guy)\b'), "blud"),
    (re.compile(r'\b(?i:everyone|everybody|guys|people|team)\b'), "chat"),
    (re.compile(r'\b(?i:money|cash|dollars)\b'), "v-bucks"),
    (re.compile(r'\b(?i:crazy|insane|weird)\b'), "straight outta ohio"),
    (re.compile(r'\b(?i:lose|lost|failed)\b'), "took an L"),
    (re.compile(r'\b(?i:win|won|success)\b'), "massive W"),
    (re.compile(r'\b(?i:charisma)\b'), "rizz"),
]

SCHIZO_RULES = [
    (re.compile(r'\b(?i:they|everyone|everybody|people|somebody|someone)\b'), "the glowies in the drywall"),
    (re.compile(r'\b(?i:police|cops|authorities|government|feds)\b'), "three-letter federal agents"),
    (re.compile(r'\b(?i:error|bug|issue|problem|crash|failure)\b'), "hardware implant telemetry breach"),
    (re.compile(r'\b(?i:internet|wifi|network|connection)\b'), "monitored DARPA frequency"),
    (re.compile(r'\b(?i:computer|pc|laptop|machine|server)\b'), "airgapped terminal"),
    (re.compile(r'\b(?i:money|cash|dollars|payment)\b'), "untraceable Monero"),
    (re.compile(r'\b(?i:phone|cell|mobile)\b'), "compromised baseband burner"),
    (re.compile(r'\b(?i:house|home|apartment|room)\b'), "faraday bunker"),
    (re.compile(r'\b(?i:car|vehicle|drive)\b'), "unmarked surveillance van"),
    (re.compile(r'\b(?i:code|software|program|script)\b'), "zero-day kernel payload"),
    (re.compile(r'\b(?i:listen|listening|hear|calling)\b'), "sniffing hypercall traps"),
    (re.compile(r'\b(?i:look|see|watching)\b'), "tracking through the fluorescent lights"),
    (re.compile(r'\b(?i:sleep|tired|rest)\b'), "subdermal microwave bombardment"),
    (re.compile(r'\b(?i:safe|good|fine|okay)\b'), "compromised by Pegasus"),
    (re.compile(r'\b(?i:secret|private|hidden)\b'), "classified black project"),
    (re.compile(r'\b(?i:meeting|talking)\b'), "surveillance trap"),
]

TRUMP_RULES = [
    (re.compile(r'\b(?i:great|awesome|amazing|fantastic|excellent)\b'), "tremendous, the greatest in the history of our country"),
    (re.compile(r'\b(?i:good|cool|nice)\b'), "very special, very high quality"),
    (re.compile(r'\b(?i:bad|terrible|horrible|awful)\b'), "a total and complete disaster, very sad"),
    (re.compile(r'\b(?i:error|bug|problem|issue|failure)\b'), "a catastrophic mess caused by incompetent fools"),
    (re.compile(r'\b(?i:smart|genius|clever)\b'), "a very stable genius with a very high IQ"),
    (re.compile(r'\b(?i:stupid|idiot|dumb|fool)\b'), "low energy, total lightweight"),
    (re.compile(r'\b(?i:money|cash|dollars)\b'), "billions and billions of dollars"),
    (re.compile(r'\b(?i:people|everyone|everybody)\b'), "many people, frankly everyone"),
    (re.compile(r'\b(?i:fix|solve|repair)\b'), "fix it fast and make it huge, believe me"),
    (re.compile(r'\b(?i:win|winning|success)\b'), "winning like nobody has ever seen before, bigly"),
    (re.compile(r'\b(?i:lose|lost|failed)\b'), "choked like a dog, total failure"),
    (re.compile(r'\b(?i:friend|bro|dude|man|guy)\b'), "great guy, fantastic person"),
    (re.compile(r'\b(?i:news|media|press)\b'), "the corrupt fake news media"),
    (re.compile(r'\b(?i:true|honestly|seriously|really)\b'), "one hundred percent true, believe me folks"),
    (re.compile(r'\b(?i:big|huge|large)\b'), "YUGE"),
    (re.compile(r'\b(?i:unfair|unjust)\b'), "treated very unfairly, nobody has been treated worse"),
]


class TextPolisher:
    def __init__(
        self,
        enabled: bool = False,
        api_url: str = "http://localhost:1234/v1/chat/completions",
        model_name: str = "local-model",
        timeout: float = 0.5,
    ):
        self.enabled = enabled
        self.api_url = api_url
        self.model_name = model_name
        self.timeout = timeout

    def transform_code(self, text: str) -> str:
        """Apply deterministic spoken code & math transformations."""
        res = text
        for pattern, repl in SPOKEN_CODE_RULES:
            res = pattern.sub(repl, res)
        return res

    def transform_uwu(self, text: str) -> str:
        """Transform natural dictation into text-only flustered submissive freak girl dialect."""
        if not text:
            return ""

        res = text
        for pat, rep in UWU_FREAK_RULES:
            res = pat.sub(rep, res)

        # r and l to w
        res = re.sub(r'[rl]', 'w', res)
        res = re.sub(r'[RL]', 'W', res)
        res = re.sub(r'\s+', ' ', res).strip()

        # Text-only suffix without symbols or emojis
        if "haah" not in res.lower():
            res = res.rstrip('.?!') + '... haah p-pwease be gentle'

        return res

    def transform_brainrot(self, text: str) -> str:
        """Transform natural dictation into Gen Alpha / TikTok Brainrot dialect (text-only, no emojis)."""
        if not text:
            return ""

        res = text
        for pat, rep in BRAINROT_RULES:
            res = pat.sub(rep, res)

        res = re.sub(r'\s+', ' ', res).strip()

        # Add brainrot flair if not present (text-only, no emojis)
        if not any(k in res.lower() for k in ["skibidi", "rizz", "gyatt", "cooked", "blud", "on god", "no cap", "fr fr", "ohio", "yap", "yapping", "fanum"]):
            res = res.rstrip('.?!') + " on god no cap fr fr"
        elif not res.lower().endswith("fr fr"):
            res = res.rstrip('.?!') + " fr fr"

        return res

    def transform_schizo(self, text: str) -> str:
        """Transform dictation into paranoid cyberpunk / glowies in the drywall rant (pure ASCII)."""
        if not text:
            return ""

        res = text
        for pat, rep in SCHIZO_RULES:
            res = pat.sub(rep, res)

        res = re.sub(r'\s+', ' ', res).strip()

        if not res.lower().startswith(('listen to me', 'do not look outside', 'they are watching', 'the walls have microphones', 'we are compromised')):
            res = "listen to me... " + res

        if not any(f in res.lower() for f in ["flush the tlb", "melt the drives", "destroy the chips", "glow in the dark", "burn the sim"]):
            res = res.rstrip('.?!') + "... flush the tlb and melt the drives right now"

        return res

    def transform_trump(self, text: str) -> str:
        """Transform dictation into Donald Trump rally rhetoric (pure ASCII)."""
        if not text:
            return ""

        res = text
        for pat, rep in TRUMP_RULES:
            res = pat.sub(rep, res)

        res = re.sub(r'\s+', ' ', res).strip()

        if not res.lower().startswith(('folks,', 'look,', 'nobody knows', 'frankly,', 'let me tell you')):
            res = "Folks, " + res[0].lower() + res[1:]

        if not any(f in res.lower() for f in ["believe me", "everyone is saying it", "nobody has seen anything like it", "witch hunt"]):
            res = res.rstrip('.?!') + ", believe me, frankly everyone is saying it."

        return res

    def generate_all_candidates(self, text: str) -> Dict[str, str]:
        """Compute all personality candidates simultaneously (<0.2 ms)."""
        return {
            "default": text,
            "brainrot": self.transform_brainrot(text),
            "uwu": self.transform_uwu(text),
            "schizo": self.transform_schizo(text),
            "trump": self.transform_trump(text),
        }

    def transform_boomer(self, text: str) -> str:
        """Transform natural dictation into ALL CAPS Facebook Dad / Boomer style."""
        if not text:
            return ""

        # Replace punctuation with ellipses
        res = re.sub(r'[,;:]|\.(?!\.\.)', '... ', text)
        res = re.sub(r'\s*\.\.\.\s*', '... ', res)
        res = re.sub(r'\s+', ' ', res).strip(' .')
        res = res.upper()

        if '-BOB' not in res:
            res = res + '... GOD BLESS... -BOB'

        return res

    def transform_gangster(self, text: str) -> str:
        """Transform natural dictation into authentic street / gangster writing style."""
        if not text:
            return ""

        res = text
        for pat, rep in GANGSTER_RULES:
            res = pat.sub(rep, res)

        def repl_ing(m):
            w = m.group(0)
            base = m.group(1)
            if w.lower() in ING_EXCEPTIONS:
                return w
            return base + "in'"

        res = re.sub(r'\b([A-Za-z]{3,})ing\b', repl_ing, res)
        res = re.sub(r'\s+', ' ', res).strip()

        if not any(f in res.lower() for f in ["nah'mean", "ya feel me", "fr fr", "wit'", "aight", "homie", "the feds"]):
            res = res.rstrip('.?!') + ", ya feel me?"

        if not res.lower().startswith(('yo', 'listen', 'look', 'man', 'aight', 'nah', 'hell yeah')):
            res = 'Yo, ' + res[0].lower() + res[1:]

        return res

    def transform_corporate(self, text: str) -> str:
        """Transform blunt/casual dictation into corporate speak."""
        if not text:
            return ""
        res = text
        for pat, rep in CORPORATE_RULES:
            res = pat.sub(rep, res)
        res = re.sub(r'\s+', ' ', res).strip()
        return res

    def transform_discord(self, text: str) -> str:
        """Transform dictation into minimalist lowercase internet/discord chat with emoji tags."""
        if not text:
            return ""
        res = text
        for pat, rep in DISCORD_RULES:
            res = pat.sub(rep, res)
        res = re.sub(r'\s+', ' ', res).strip()
        return res.lower().rstrip('. ')

    def transform_victorian(self, text: str) -> str:
        """Transform dictation into grandiloquent Victorian / Gothic prose."""
        if not text:
            return ""
        res = text
        for pat, rep in VICTORIAN_RULES:
            res = pat.sub(rep, res)
        res = re.sub(r'\s+', ' ', res).strip()
        return res

    def polish(self, text: str, style: str = "") -> str:
        """Clean and polish text using local SLM endpoint if available, with deterministic fallback."""
        if not text:
            return ""

        if style == "uwu":
            deterministic = self.transform_uwu(text)
        elif style == "brainrot":
            deterministic = self.transform_brainrot(text)
        elif style == "schizo":
            deterministic = self.transform_schizo(text)
        elif style == "trump":
            deterministic = self.transform_trump(text)
        elif style == "boomer":
            deterministic = self.transform_boomer(text)
        elif style == "gangster":
            deterministic = self.transform_gangster(text)
        elif style == "corporate":
            deterministic = self.transform_corporate(text)
        elif style == "discord":
            deterministic = self.transform_discord(text)
        elif style == "victorian":
            deterministic = self.transform_victorian(text)
        else:
            deterministic = self.transform_code(text)

        if not self.enabled:
            return deterministic

        prompts = {
            "uwu": (
                "Rewrite the following spoken sentence into flustered submissive freak girl style. "
                "Replace r/l with w, add submissive stutters (p-pwease, s-sawwy, y-yes sir haah), and needy expressions. "
                "Do NOT use any emojis, kaomoji, or special symbols. Return ONLY plain text words.\n\n"
                f"Input: {text}\nOutput:"
            ),
            "brainrot": (
                "Rewrite the following spoken sentence into Gen Alpha / TikTok Brainrot dialect. "
                "Use slang terms like skibidi, sigma, rizzler, gyatt, fanum tax, ohio, blud, yapping, mewing, cooked, on god no cap fr fr. "
                "Do NOT use any emojis or symbols. Return ONLY plain text words.\n\n"
                f"Input: {text}\nOutput:"
            ),
            "schizo": (
                "Rewrite the following spoken sentence into paranoid, dark-web / cyberpunk schizo style. "
                "Reference the glowies in the drywall, three-letter federal agents, hardware implant telemetry, "
                "monitored DARPA frequencies, sniffing hypercall traps, and flushing the TLB. "
                "Do NOT use any emojis or symbols. Return ONLY plain text words.\n\n"
                f"Input: {text}\nOutput:"
            ),
            "trump": (
                "Rewrite the following spoken sentence into Donald Trump rally rhetoric. "
                "Use classic phrases like Folks, tremendous, total disaster, believe me, "
                "nobody knows it better than me, billions and billions, winning bigly, frankly everyone is saying it. "
                "Do NOT use any emojis or symbols. Return ONLY plain text words.\n\n"
                f"Input: {text}\nOutput:"
            ),
            "boomer": (
                "Rewrite the following spoken sentence into Facebook Dad / Boomer typing style. "
                "Use ALL CAPS, excessive ellipses (...), and sign off with ... GOD BLESS... -BOB. "
                "Do not add commentary or quotes, return ONLY the rewritten text.\n\n"
                f"Input: {text}\nOutput:"
            ),
            "gangster": (
                "Rewrite the following spoken sentence into authentic modern street slang / gangster style. "
                "Keep the core meaning, but adapt vocabulary to street slang and contractions. "
                "Do not add commentary or quotes, return ONLY the rewritten text.\n\n"
                f"Input: {text}\nOutput:"
            ),
            "corporate": (
                "Rewrite the following spoken sentence into polished corporate enterprise speak. "
                "Sanitize bluntness with professional corporate buzzwords (alignment, bandwidth, touch base). "
                "Do not add commentary or quotes, return ONLY the rewritten text.\n\n"
                f"Input: {text}\nOutput:"
            ),
            "discord": (
                "Rewrite the following spoken sentence into minimalist internet/Discord chat. "
                "Use all-lowercase and text abbreviations (tbh, ngl, fr, idk, dead, bruh). "
                "Do NOT use any emojis or symbols. Return ONLY plain text.\n\n"
                f"Input: {text}\nOutput:"
            ),
            "victorian": (
                "Rewrite the following spoken sentence into dramatic, grandiloquent Victorian / 19th-century English. "
                "Use archaic phrasing (thou, methinks, verily, alas). "
                "Do not add commentary or quotes, return ONLY the rewritten text.\n\n"
                f"Input: {text}\nOutput:"
            ),
        }

        prompt = prompts.get(
            style,
            (
                "You are a dictation polisher. Fix any transcription errors, clean grammar, "
                "and format correctly. Do not add commentary or quotes, return ONLY the polished text.\n\n"
                f"Input: {text}\nOutput:"
            )
        )

        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3 if style in prompts else 0.2,
            "max_tokens": 128,
        }

        try:
            req = urllib.request.Request(
                self.api_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    choices = data.get("choices", [])
                    if choices:
                        polished = choices[0].get("message", {}).get("content", "").strip()
                        if polished:
                            return polished
        except Exception:
            pass

        return deterministic
