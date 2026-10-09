export function isTextFile(file) {
    return file.type === "text/plain" || /\.txt$/i.test(file.name || "");
}

function fileToDataUrl(file) {
    return new Promise(function(resolve, reject) {
        var reader = new FileReader();
        reader.onload = function() { resolve(reader.result); };
        reader.onerror = function() { reject(reader.error); };
        reader.readAsDataURL(file);
    });
}

function fileToText(file) {
    return new Promise(function(resolve, reject) {
        var reader = new FileReader();
        reader.onload = function() { resolve(reader.result || ""); };
        reader.onerror = function() { reject(reader.error); };
        reader.readAsText(file);
    });
}

export async function buildUserContent(text, files) {
    if (!files.length) return text;
    var parts = [];
    if (text) parts.push({ type: "text", text: text });
    for (var i = 0; i < files.length; i += 1) {
        if (isTextFile(files[i])) {
            var fileText = await fileToText(files[i]);
            parts.push({
                type: "text",
                text: [
                    '[Attached text file: "' + files[i].name + '"]',
                    fileText,
                    '[End attached text file: "' + files[i].name + '"]'
                ].join("\n")
            });
        } else {
            parts.push({
                type: "image_url",
                image_url: { url: await fileToDataUrl(files[i]) }
            });
        }
    }
    return parts;
}
