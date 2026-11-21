package vn.tdtu.securechat;

import android.app.Activity;
import android.content.Intent;
import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.view.WindowInsets;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.io.IOException;
import java.security.cert.CertificateException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import javax.net.ssl.SSLPeerUnverifiedException;
import org.json.JSONArray;
import org.json.JSONObject;

public final class ChatActivity extends Activity {
    private static final int INK = Color.rgb(19, 36, 61);
    private static final int MUTED = Color.rgb(63, 81, 110);
    private static final int BLUE = Color.rgb(23, 75, 148);
    private static final String TAG = "SecureChat";
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final ChatApi api = new ChatApi();
    private MessageCache cache;
    private ScrollView conversation;
    private LinearLayout messages;
    private TextView status;
    private EditText input;
    private Button send;
    private Button refresh;

    @Override protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        cache = new MessageCache(this);
        LinearLayout root = column();
        root.setBackgroundColor(Color.rgb(244, 247, 252));
        root.setOnApplyWindowInsetsListener((v, insets) -> {
            var bounds = insets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.ime());
            v.setPadding(bounds.left + dp(16), bounds.top + dp(10),
                    bounds.right + dp(16), bounds.bottom + dp(6));
            return insets;
        });
        conversation = new ScrollView(this);
        LinearLayout feed = column();
        conversation.addView(feed);
        root.addView(conversation, new LinearLayout.LayoutParams(-1, 0, 1));
        TextView title = text("Secure Chat", 33, INK);
        title.setTypeface(null, Typeface.BOLD);
        title.setAccessibilityHeading(true);
        feed.addView(title);
        feed.addView(text(BuildConfig.POLICY + " policy  /  Local HTTPS", 15, MUTED));
        status = text("Opening encrypted cache…", 15, INK);
        status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        status.setPadding(dp(14), dp(13), dp(14), dp(13));
        status.setBackground(card(Color.rgb(227, 237, 252)));
        addSpaced(feed, status, 12);
        TextView heading = text("Conversation", 17, INK);
        heading.setTypeface(null, Typeface.BOLD);
        heading.setAccessibilityHeading(true);
        addSpaced(feed, heading, 12);
        messages = column();
        feed.addView(messages);

        input = new EditText(this);
        input.setSingleLine(true);
        input.setHint("Write a sample message");
        input.setContentDescription("Message text");
        input.setTextColor(INK);
        input.setHintTextColor(MUTED);
        input.setInputType(android.text.InputType.TYPE_CLASS_TEXT);
        input.setImeOptions(EditorInfo.IME_ACTION_SEND | EditorInfo.IME_FLAG_NO_EXTRACT_UI);
        input.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(280)});
        addSpaced(root, input, 8);

        LinearLayout actions = new LinearLayout(this);
        send = button("Send message");
        refresh = button("Refresh");
        var primary = new LinearLayout.LayoutParams(0, dp(52), 1.35f);
        primary.setMarginEnd(dp(8));
        actions.addView(send, primary);
        actions.addView(refresh, new LinearLayout.LayoutParams(0, dp(52), 1));
        addSpaced(root, actions, 5);
        setContentView(root);
        root.setFocusableInTouchMode(true);
        root.requestFocus();

        send.setOnClickListener(v -> sendDraft());
        input.setOnEditorActionListener((v, action, event) -> {
            if (action != EditorInfo.IME_ACTION_SEND) return false;
            sendDraft();
            return true;
        });
        refresh.setOnClickListener(v -> network(null));
        busy(true);
        worker.execute(() -> {
            try {
                JSONArray savedMessages = cache.load();
                present(() -> {
                    showMessages(savedMessages);
                    status.setText(savedMessages.length() == 0
                            ? "Ready · Tap Refresh to check TLS"
                            : "Encrypted cache restored · " + savedMessages.length() + " message(s)");
                });
            } catch (Exception error) {
                present(() -> status.setText("Encrypted cache rejected · Tap Refresh to retry"));
            }
        });
    }

    private void sendDraft() {
        if (!send.isEnabled()) return;
        String message = input.getText().toString().strip();
        if (message.isEmpty()) {
            setStatus("Enter a message before sending.", false);
            return;
        }
        ((InputMethodManager) getSystemService(Context.INPUT_METHOD_SERVICE))
                .hideSoftInputFromWindow(input.getWindowToken(), 0);
        network(message);
    }

    private void network(String text) {
        busy(true);
        setStatus("Connecting over HTTPS…", false);
        worker.execute(() -> {
            try {
                JSONArray fresh = text == null ? api.messages() : api.send(text);
                String outcome = text == null ? "TLS accepted · Conversation loaded" : "TLS accepted · Message sent";
                try {
                    cache.save(fresh);
                } catch (Exception error) {
                    present(() -> {
                        if (text != null) input.setText("");
                        showMessages(fresh);
                        // The visible response still came from HTTPS, even if the disk write failed.
                        setStatus(outcome + " · Encrypted cache unavailable", true);
                    });
                    return;
                }
                Log.i(TAG, BuildConfig.POLICY + " TLS accepted");
                present(() -> {
                    if (text != null) input.setText("");
                    showMessages(fresh);
                    setStatus(outcome, false);
                });
            } catch (IOException | org.json.JSONException error) {
                boolean identityRefused = serverIdentityRefused(error);
                if (identityRefused) {
                    Log.i(TAG, BuildConfig.POLICY + " TLS refused", error);
                } else {
                    Log.i(TAG, BuildConfig.POLICY + " request failed: " + error.getClass().getSimpleName());
                }
                present(() -> setStatus(identityRefused
                        ? "TLS refused · Server identity could not be verified"
                        : "Connection unavailable · Check the lab server", true));
            }
        });
    }

    private void setStatus(String value, boolean warning) {
        status.setText(value);
        status.setBackground(card(warning ? Color.rgb(255, 234, 222) : Color.rgb(227, 237, 252)));
        conversation.scrollTo(0, 0);
    }

    private static boolean serverIdentityRefused(Throwable error) {
        for (Throwable cause = error; cause != null; cause = cause.getCause()) {
            if (cause instanceof CertificateException || cause instanceof SSLPeerUnverifiedException) {
                return true;
            }
        }
        return false;
    }

    private void present(Runnable action) {
        runOnUiThread(() -> {
            if (!isFinishing() && !isDestroyed()) {
                action.run();
                busy(false);
            }
        });
    }

    private void busy(boolean value) {
        send.setEnabled(!value);
        refresh.setEnabled(!value);
        input.setEnabled(!value);
    }

    private void showMessages(JSONArray data) {
        messages.removeAllViews();
        if (data.length() == 0) addSpaced(messages, text("No messages yet.", 15, MUTED), 12);
        for (int i = data.length() - 1; i >= 0; i--) {
            JSONObject message = data.optJSONObject(i);
            if (message == null || message.optInt("id") <= 0) continue;
            int id = message.optInt("id");
            Button row = button("Message #" + id + "  ·  " + message.optString("text"));
            row.setBackgroundTintList(ColorStateList.valueOf(Color.WHITE));
            row.setTextColor(INK);
            row.setOnClickListener(v -> startActivity(new Intent(this, DetailActivity.class).putExtra("id", id)));
            addSpaced(messages, row, 6);
        }
    }

    private Button button(String label) {
        Button button = new Button(this);
        button.setText(label);
        button.setAllCaps(false);
        button.setTextColor(Color.WHITE);
        button.setMinHeight(dp(48));
        button.setBackgroundTintList(ColorStateList.valueOf(BLUE));
        return button;
    }

    private TextView text(String value, int size, int color) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setTextColor(color);
        return view;
    }

    private LinearLayout column() {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        return layout;
    }

    private void addSpaced(LinearLayout parent, View child, int top) {
        var layout = new LinearLayout.LayoutParams(-1, -2);
        layout.topMargin = dp(top);
        parent.addView(child, layout);
    }

    private GradientDrawable card(int color) {
        GradientDrawable background = new GradientDrawable();
        background.setColor(color);
        background.setCornerRadius(dp(12));
        return background;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    @Override protected void onDestroy() {
        worker.shutdown();
        super.onDestroy();
    }
}
