export function escapeHtml(value) {
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function safeLinkUrl(value) {
    var url = String(value || "").trim();
    return /^(https?:\/\/|mailto:)/i.test(url) ? url : "#";
}

export function renderInlineMarkdown(text) {
    var codeTokens = [];
    var linkTokens = [];
    var tokenized = String(text).replace(/`([^`]+)`/g, function(match, code) {
        var token = "\u0000CODE" + codeTokens.length + "\u0000";
        codeTokens.push("<code>" + escapeHtml(code) + "</code>");
        return token;
    });
    tokenized = tokenized.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, function(match, label, url) {
        var href = escapeHtml(safeLinkUrl(url));
        var rel = href === "#" ? "" : " rel=\"noreferrer\" target=\"_blank\"";
        var token = "\u0000LINK" + linkTokens.length + "\u0000";
        var labelHtml = escapeHtml(label)
            .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
            .replace(/\*([^*]+)\*/g, "<em>$1</em>");
        linkTokens.push("<a href=\"" + href + "\"" + rel + ">" + labelHtml + "</a>");
        return token;
    });
    var html = escapeHtml(tokenized);
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    linkTokens.forEach(function(tokenHtml, index) {
        html = html.replace("\u0000LINK" + index + "\u0000", function() { return tokenHtml; });
    });
    codeTokens.forEach(function(tokenHtml, index) {
        html = html.replace("\u0000CODE" + index + "\u0000", function() { return tokenHtml; });
    });
    return html;
}

export function markdownToHtml(markdown) {
    var lines = String(markdown || "").replace(/\r\n?/g, "\n").split("\n");
    var html = [];
    var paragraph = [];
    var listItems = [];
    var listType = null;
    var codeLines = [];
    var inCode = false;

    function flushParagraph() {
        if (!paragraph.length) return;
        html.push("<p>" + renderInlineMarkdown(paragraph.join(" ")) + "</p>");
        paragraph = [];
    }

    function flushList() {
        if (!listItems.length) return;
        html.push("<" + listType + ">" + listItems.join("") + "</" + listType + ">");
        listItems = [];
        listType = null;
    }

    function flushCode() {
        html.push("<pre><code>" + escapeHtml(codeLines.join("\n")) + "</code></pre>");
        codeLines = [];
    }

    lines.forEach(function(line) {
        var fenceMatch = line.match(/^```/);
        var headingMatch = line.match(/^(#{1,3})\s+(.+)$/);
        var listMatch = line.match(/^\s*([-*+]|\d+[.)])\s+(.+)$/);
        var quoteMatch = line.match(/^>\s?(.*)$/);

        if (fenceMatch) {
            if (inCode) {
                flushCode();
                inCode = false;
            } else {
                flushParagraph();
                flushList();
                inCode = true;
            }
            return;
        }

        if (inCode) {
            codeLines.push(line);
            return;
        }

        if (!line.trim()) {
            flushParagraph();
            flushList();
            return;
        }

        if (headingMatch) {
            flushParagraph();
            flushList();
            var level = headingMatch[1].length;
            html.push("<h" + level + ">" + renderInlineMarkdown(headingMatch[2]) + "</h" + level + ">");
            return;
        }

        if (listMatch) {
            flushParagraph();
            var nextType = /^\d/.test(listMatch[1]) ? "ol" : "ul";
            if (listType && listType !== nextType) flushList();
            listType = nextType;
            listItems.push("<li>" + renderInlineMarkdown(listMatch[2]) + "</li>");
            return;
        }

        if (quoteMatch) {
            flushParagraph();
            flushList();
            html.push("<blockquote>" + renderInlineMarkdown(quoteMatch[1]) + "</blockquote>");
            return;
        }

        flushList();
        paragraph.push(line.trim());
    });

    if (inCode) flushCode();
    flushParagraph();
    flushList();
    return html.join("");
}
