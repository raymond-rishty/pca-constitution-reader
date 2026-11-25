package org.pcareader.preview;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertThrows;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

public class ReaderUpdatesTest {
    @Rule
    public TemporaryFolder storage = new TemporaryFolder();

    @Test
    public void extractsAnOfflineReader() throws IOException {
        File output = storage.newFolder();
        ReaderUpdates.unpack(zip("index.html", "android-reader.js", "content/cit/bco-1.js"), output);
        assertEquals("content/cit/bco-1.js",
            new String(Files.readAllBytes(new File(output, "content/cit/bco-1.js").toPath()), StandardCharsets.UTF_8));
    }

    @Test
    public void rejectsUnsafeArchivePaths() throws IOException {
        File output = storage.newFolder();
        assertThrows(IOException.class, () -> ReaderUpdates.unpack(zip("../index.html"), output));
        assertThrows(IOException.class, () -> ReaderUpdates.unpack(zip("content/../../index.html"), output));
        assertThrows(IOException.class, () -> ReaderUpdates.unpack(zip("content\\index.html"), output));
    }

    @Test
    public void rejectsIncompleteReader() throws IOException {
        File output = storage.newFolder();
        assertThrows(IOException.class, () -> ReaderUpdates.unpack(zip("index.html"), output));
    }

    private byte[] zip(String... paths) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ZipOutputStream zip = new ZipOutputStream(bytes)) {
            for (String path : paths) {
                zip.putNextEntry(new ZipEntry(path));
                zip.write(path.getBytes(StandardCharsets.UTF_8));
                zip.closeEntry();
            }
        }
        return bytes.toByteArray();
    }
}
