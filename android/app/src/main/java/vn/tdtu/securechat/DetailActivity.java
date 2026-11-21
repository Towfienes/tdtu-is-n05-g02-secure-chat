package vn.tdtu.securechat;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.view.Gravity;
import android.widget.TextView;
import org.json.JSONArray;
import org.json.JSONObject;

public final class DetailActivity extends Activity {
    static int messageId(Intent intent) {
        int value = intent.getIntExtra("id", -1);
        return value > 0 ? value : -1;
    }

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        int id = messageId(getIntent());
        String result = id > 0 ? "Message unavailable" : "Invalid message ID";
        if (id > 0) {
            try {
                JSONArray messages = new MessageCache(this).load();
                for (int i = 0; i < messages.length(); i++) {
                    JSONObject message = messages.getJSONObject(i);
                    if (message.getInt("id") == id) {
                        result = "Message #" + id + "\n\n" + message.getString("text");
                        break;
                    }
                }
            } catch (Exception error) {
                result = "Encrypted cache unavailable";
            }
        }
        TextView body = new TextView(this);
        body.setGravity(Gravity.CENTER);
        body.setTextSize(23);
        body.setPadding(36, 36, 36, 36);
        body.setText(result);
        setContentView(body);
    }
}
