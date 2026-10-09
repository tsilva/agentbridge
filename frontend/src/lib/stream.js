export function parseSseEvent(buffer, onData) {
    // Keep a final CR until the next read, since CRLF can span chunks.
    buffer = buffer.replace(/\r\n/g, "\n").replace(/\r(?!$)/g, "\n");
    var events = buffer.split(/\n\n/);
    var remainder = events.pop();
    events.forEach(function(event) {
        var dataLines = event.split(/\n/).filter(function(line) {
            return line.indexOf("data:") === 0;
        }).map(function(line) {
            return line.slice(5).trimStart();
        });
        if (dataLines.length) onData(dataLines.join("\n"));
    });
    return remainder;
}

export async function streamResponse(response, onDelta) {
    var reader = response.body.getReader();
    var decoder = new TextDecoder();
    var buffer = "";
    var completed = false;
    var text = "";

    function streamError(message, code, details) {
        var error = new Error(message);
        error.type = "stream_error";
        error.details = details || { error: { message: message, type: "stream_error", code: code } };
        return error;
    }

    function onData(data) {
        if (completed) return;
        if (data === "[DONE]") {
            completed = true;
            return;
        }
        var chunk;
        try {
            chunk = JSON.parse(data);
        } catch (e) {
            throw streamError("Invalid JSON in streaming response.", "invalid_stream");
        }
        if (chunk && chunk.error) {
            throw streamError(chunk.error.message || "Streaming request failed", "provider_error", chunk);
        }
        if (!chunk || !Array.isArray(chunk.choices)) {
            throw streamError("Invalid streaming response.", "invalid_stream");
        }
        var choice = chunk.choices[0];
        var delta = choice && choice.delta && choice.delta.content;
        if (delta !== undefined && delta !== null && typeof delta !== "string") {
            throw streamError("Invalid streaming content.", "invalid_stream");
        }
        if (delta) { text += delta; onDelta(delta); }
    }

    try {
        while (!completed) {
            var read = await reader.read();
            if (read.done) {
                buffer += decoder.decode();
                parseSseEvent(buffer.replace(/\r$/, "\n"), onData);
                break;
            }
            buffer += decoder.decode(read.value, { stream: true });
            buffer = parseSseEvent(buffer, onData);
        }
        if (!completed) {
            throw streamError("The response stream ended before completion. Retry the request.", "incomplete_stream");
        }
        return text;
    } finally {
        await reader.cancel().catch(function() {});
        reader.releaseLock();
    }
}
