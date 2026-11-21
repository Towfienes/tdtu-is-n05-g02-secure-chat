package vn.tdtu.securechat;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import javax.net.ssl.HttpsURLConnection;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

final class ChatApi {
    private static final String ENDPOINT = "https://localhost:8443/messages";

    JSONArray messages() throws IOException, JSONException {
        return new JSONArray(request(null));
    }

    JSONArray send(String text) throws IOException, JSONException {
        return new JSONArray(request(new JSONObject().put("text", text).toString()));
    }

    private String request(String body) throws IOException {
        HttpsURLConnection connection = (HttpsURLConnection) new URL(ENDPOINT).openConnection();
        connection.setConnectTimeout(3500);
        connection.setReadTimeout(3500);
        connection.setInstanceFollowRedirects(false);
        try {
            if (body != null) {
                byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
                connection.setRequestMethod("POST");
                connection.setDoOutput(true);
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                connection.setFixedLengthStreamingMode(bytes.length);
                try (OutputStream output = connection.getOutputStream()) {
                    output.write(bytes);
                }
            }
            int status = connection.getResponseCode();
            if (status != (body == null ? 200 : 201)) throw new IOException("Unexpected HTTP status " + status);
            try (InputStream input = connection.getInputStream()) {
                byte[] bytes = input.readNBytes(65537);
                if (bytes.length > 65536) throw new IOException("Response exceeded 64 KiB");
                return new String(bytes, StandardCharsets.UTF_8);
            }
        } finally {
            connection.disconnect();
        }
    }
}
