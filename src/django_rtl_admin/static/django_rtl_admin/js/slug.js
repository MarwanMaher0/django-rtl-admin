/* Arabic/Persian slug prepopulation for fields marked by BidiSafeAdminMixin. */
(() => {
    "use strict";

    const $ = django.jQuery;
    const stockPrepopulate = $.fn.prepopulate;
    // Keep this letter table in sync with formatting.arabic_slugify and the API docs.
    const letters = new Map();
    for (const [chars, latin] of [
        ["اأإآٱءعى", "a"], ["ب", "b"], ["تط", "t"], ["ث", "th"],
        ["ج", "j"], ["حةهہۀە", "h"], ["خ", "kh"], ["دض", "d"],
        ["ذ", "dh"], ["ر", "r"], ["زظ", "z"], ["سص", "s"], ["ش", "sh"],
        ["غ", "gh"], ["ف", "f"], ["ق", "q"], ["كک", "k"], ["ل", "l"],
        ["م", "m"], ["ن", "n"], ["وؤ", "w"], ["يیئ", "y"],
        ["پ", "p"], ["چ", "ch"], ["ژ", "zh"], ["گ", "g"],
    ]) {
        for (const char of chars) letters.set(char, latin);
    }
    const ignored = /[\u061c\u0640\u064b-\u065f\u0670\u200e\u200f\u202a-\u202e\u2066-\u2069]/g;
    const digits = "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹";
    const arabic = /[\u0600-\u06ff\u0750-\u077f\u0870-\u08ff\ufb50-\ufdff\ufe70-\ufefc\u{10ec0}-\u{10eff}\u{1ee00}-\u{1eeff}]/u;
    // Python's whitespace set differs slightly from JavaScript's \s.
    const whitespace = /[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]/g;

    function slugify(value, allowUnicode, limit) {
        let text = (allowUnicode ? value : value.normalize("NFKC"))
            .replace(ignored, "")
            .replace(/[٠-٩۰-۹]/g, (digit) => String(digits.indexOf(digit) % 10));
        if (allowUnicode) {
            text = text.normalize("NFKC");
        } else {
            text = Array.from(text, (char) => letters.get(char) ?? char).join("")
                .normalize("NFKD").replace(/[^\x00-\x7f]/g, "");
        }
        // Strip the same punctuation Python does, before collapsing separators.
        text = text.toLowerCase().replace(whitespace, " ").replace(/[^\p{L}\p{N}_ -]/gu, "");
        // URLify's bundled Unicode categories can lag behind the browser's
        // and omit some letters. Use its separator rule directly in Unicode mode.
        const joined = allowUnicode
            ? text.replace(/[- ]+/g, "-")
            : window.URLify(text, text.length, false);
        const slug = joined.replace(/^[-_]+|[-_]+$/g, "") ||
            (!allowUnicode && arabic.test(value) ? "arabic" : "");
        // Count code points as Python does, and prefer complete segments.
        const chars = Array.from(slug);
        if (chars.length <= limit) return slug;
        if (limit <= 0) return "";
        const boundary = chars.lastIndexOf("-", limit);
        return chars.slice(0, boundary === -1 ? limit : boundary).join("").replace(/[-_]+$/, "");
    }

    // Django calls this plugin for the main form, initial inline rows and
    // dynamically cloned rows. The widget marker travels with each clone and
    // carries allow_unicode (which stock inlines omit when cloning a row).
    $.fn.prepopulate = function(dependencies, maxLength, allowUnicode) {
        return this.each(function() {
            const field = $(this);
            const mode = this.dataset.rtlSlug;
            if (!mode) {
                stockPrepopulate.call(field, dependencies, maxLength, allowUnicode);
                return;
            }
            if (mode === "off" || field.val() || this.closest(".empty-form")) return;
            const length = this.dataset.rtlSlugLength;
            const limit = length === "" ? Infinity : Number(length);
            const sources = dependencies.map((dependency) => $(dependency));
            let edited = false;
            field.on("input change", () => { edited = true; });
            $(dependencies.join(",")).on("input change focus", () => {
                if (edited) return;
                const source = sources.map((input) => input.val() ?? "").join(" ");
                field.val(slugify(source, mode === "unicode", limit));
            });
        });
    };
})();
