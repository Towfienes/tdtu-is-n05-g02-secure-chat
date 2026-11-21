package vn.tdtu.securechat;

import static org.junit.Assert.*;

import android.content.Context;
import android.content.Intent;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import javax.crypto.AEADBadTagException;
import org.json.JSONArray;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public class CacheTest {
    private final Context context =
            InstrumentationRegistry.getInstrumentation().getTargetContext();

    @Test public void encryptedCacheSurvivesReopenAndRejectsChanges() throws Exception {
        String marker = "TDTU_DEMO_SYNTHETIC_72";
        JSONArray messages = new JSONArray("[{\"id\":7,\"text\":\"" + marker + "\"}]");
        MessageCache cache = new MessageCache(context);
        byte[] previous = cache.file().exists() ? Files.readAllBytes(cache.file().toPath()) : null;
        try {
            cache.save(messages);
            byte[] first = Files.readAllBytes(cache.file().toPath());
            assertFalse(new String(first, StandardCharsets.ISO_8859_1).contains(marker));
            assertEquals(marker, new MessageCache(context).load().getJSONObject(0).getString("text"));

            cache.save(messages);
            byte[] second = Files.readAllBytes(cache.file().toPath());
            assertFalse(java.util.Arrays.equals(first, second));
            second[second.length - 1] ^= 1;
            Files.write(cache.file().toPath(), second);
            assertThrows(AEADBadTagException.class, cache::load);
        } finally {
            if (previous != null) Files.write(cache.file().toPath(), previous);
            else Files.deleteIfExists(cache.file().toPath());
        }
    }

    @Test public void detailIsPrivateAndIdIsValidated() throws Exception {
        Intent intent = new Intent(context, DetailActivity.class);
        assertFalse(context.getPackageManager().getActivityInfo(intent.getComponent(), 0).exported);
        assertEquals(-1, DetailActivity.messageId(intent));
        assertEquals(-1, DetailActivity.messageId(intent.putExtra("id", "7")));
        assertEquals(-1, DetailActivity.messageId(intent.putExtra("id", 0)));
        assertEquals(7, DetailActivity.messageId(intent.putExtra("id", 7)));
    }
}
