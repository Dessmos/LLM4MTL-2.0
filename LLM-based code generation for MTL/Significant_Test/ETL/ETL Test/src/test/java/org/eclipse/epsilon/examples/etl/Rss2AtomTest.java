package org.eclipse.epsilon.examples.etl;

import static org.junit.jupiter.api.Assertions.*;

import java.io.File;
import java.util.Collection;

import org.eclipse.epsilon.emc.plainxml.PlainXmlModel;
import org.eclipse.epsilon.eol.models.IModel;
import org.eclipse.epsilon.etl.EtlModule;
import org.junit.jupiter.api.Test;

public class Rss2AtomTest extends EtlTestBase {

    @Test
    public void testRss2Atom() throws Exception {
        // Create RSS source model (PlainXML)
        PlainXmlModel rssModel = new PlainXmlModel();
        rssModel.setName("RSS");
        rssModel.setFile(new File(getResourcePath("xml/rss.xml")));
        rssModel.setReadOnLoad(true);
        rssModel.setStoredOnDisposal(false);
        rssModel.load();
        models.add(rssModel);

        // Create Atom target model (PlainXML)
        File atomFile = File.createTempFile("atom_output", ".xml");
        atomFile.deleteOnExit();
        PlainXmlModel atomModel = new PlainXmlModel();
        atomModel.setName("Atom");
        atomModel.setFile(atomFile);
        atomModel.setReadOnLoad(false);
        atomModel.setStoredOnDisposal(false);
        atomModel.load();
        models.add(atomModel);

        runEtl("transformations/rss2atom.etl", rssModel, atomModel);

        // Verify feed element exists
        Collection<?> feeds = atomModel.getAllOfType("t_feed");
        assertEquals(1, feeds.size(), "Should have 1 feed element");

        // Verify entries were created (RSS has 10 items)
        Collection<?> entries = atomModel.getAllOfType("t_entry");
        assertEquals(10, entries.size(), "Entry count should match RSS item count");

        // Verify entries have titles
        Collection<?> titles = atomModel.getAllOfType("t_title");
        assertFalse(titles.isEmpty(), "Entries should have title elements");

        // Verify entries have published dates
        Collection<?> published = atomModel.getAllOfType("t_published");
        assertFalse(published.isEmpty(), "Entries should have published elements");
    }
}
