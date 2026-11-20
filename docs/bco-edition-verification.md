# English BCO edition verification

The English reader was reconciled on November 20, 2026 against the PCA Office of the Stated Clerk's [official 2026 English PDF](https://www.pcaac.org/wp-content/uploads/2026/11/BCO_2026.pdf). The cover gives the 53rd General Assembly in Louisville, Kentucky, June 22–26, 2026 as the amendment cutoff. The Publisher's Introduction still refers to the 2025 update. The cover, copyright, and amendment chronology identify the edition.

The audit covered 76 ordered entries and 439 numbered provisions, including eight Preliminary Principles. It covered the printed Preface through Appendix J (PDF pages 9–242), including the Directory for Worship's introductory statement and the Appendix H flowchart (PDF page 231). The cover and amendment chronology establish the edition and the list of changes. The publisher's other introductory pages, printed contents and index, and companion documents fall outside the English text bundled in `content/bco.js`.

The previous reader already included the wording of all 11 provisions listed in the 2026 amendment chronology (PDF page 4). These are 12-3, 18-2, 24-1, 29-1 (editorial), 31-10, 35-9, 36-4, 36-5, 36-8, 41-3, and 42-2. The audit also confirms that the official English PDF includes 35-16 and prints 56-6 as a separate provision, with its number followed by a space.

## Corrections to the reader

| Location | What changed |
| --- | --- |
| Preface (PDF pp. 9–11) | Restored the headings for Parts II and III of the Preface. Edition information now appears in Home and About. Removed the web copyright footer from the Preface body. |
| Chapter headings | Restored the opening subheadings in chapters 5, 19, 24, and 56. Moved the next subheadings in chapters 5, 19, and 24 out of the preceding provisions and placed them before 5-9, 19-7, and 24-6. Completed the truncated titles of chapters 34 and 39. Matched the dash spacing in chapter 7's title. |
| 5-10, 11-4, 13-2, 19-2(a), and 47-3 | Lowercased the second occurrence of “session” in 5-10, restored the final period in 11-4, capitalized “Presbytery” in the 13-2 editorial comment, restored the colon at the end of 19-2(a), and spaced the em dash in 47-3. |
| 13-9, 14-6, 15-5, and 21-5 through 21-9 | Set the existing editorial notes apart from the numbered items, restored spacing in 15-5(c)(1), and formatted the five assistant-minister note markers as superscripts. Restored the final period in note 3 at 21-7. |
| Directory for Worship (PDF p. 155) | Restored the omitted introductory statement explaining the Directory's authority and identifying chapters 56–58 and 59-3 as constitutionally binding. |
| Appendices introduction (PDF p. 191) | Restored the omitted editorial note on the appendices' authority and the introduction to the optional forms. Both appear at the start of Appendix A, where the reader begins its appendices. |
| Appendices E and G (PDF pp. 213, 223) | Restored Appendix E's footnote crediting John Knox's liturgy. Removed a running page header embedded in Appendix G's text. |
| Appendix H (PDF pp. 229–231) | Restored omitted item 14, which directs the stated clerk to send the commission's decision and any separate opinions to the parties and presbytery members. Restored two commas in the summary and placed the existing flowchart after the text in print order. Its labels, timing, and connections match the 2026 PDF. |
| Appendices I and J (PDF pp. 233–242) | Rejoined three split paragraphs in Appendix I and matched the printed capitalization of its arbitration notice. In Appendix J, grouped the tax bullets under the two salary headings, set off the retirement-plan note, and removed the web footer. |

The comparison allows equivalent whitespace, dash, quote and ellipsis glyphs, and form-line spacing. It reads notes with their owning provisions and handles the two form columns in Appendices I and J. It checks wording and order for every entry and verifies that structured blocks reproduce the body. Printed page layout, page headers, and the PDF's amendment bullets and underlining serve as review evidence. The reader uses its own reflowable layout.

## Repeat the comparison

1. Download the edition PDF from the Office of the Stated Clerk. Record its URL and SHA-256, cover cutoff, and the amendment references from its chronology. For the verified 2026 PDF the SHA-256 is `d4f8f1d17e33a85ee89220dbb297ee1aab02e51e5c52575f46e1187079828210`.
2. With Python and Poppler's `pdftotext` on PATH, run the comparison below. It was verified with Poppler 26.09.0 and the [edition builder at revision 5b7cd58](https://github.com/raymond-rishty/pca-reader-content-packs/blob/5b7cd589c0431ec42a8c6666a5b8f398b954cb87/tools/build_bco_edition.py).

   ```sh
   python tools/verify_bco_edition.py /path/to/BCO_2026.pdf --builder ../pca-reader-content-packs/tools/build_bco_edition.py
   ```

3. For a new edition, review the extractor's page boundaries and edition-specific adjustments against the new PDF. Inspect every discrepancy in the comparison and check every amendment cited by the new edition. Confirm missing passages, footnotes, headings, and diagrams against the actual pages. The older HTML and block generators can make a comparison copy in a scratch checkout. Their output requires reconciliation with the PDF before it replaces the bundled English asset.
4. Update the bundled English edition metadata in `content/bco.js` after resolving the differences. Home reads the active language's edition, and About & Sources cites the verified English source and identifies the bundled translations. Review the Spanish and Korean notices against their own editions.
5. Change the service worker cache version. Serve the previous and candidate revisions in turn from the same local origin with the same browser profile. Wait for the previous worker to control the page, switch to the candidate, then refresh. Check that the edition notice, a corrected provision, and Appendix H's figure update. Go offline and reopen a provision to verify that the updated app shell and English data are cached together.
6. After the Pages build publishes the release commit, repeat the refresh with a browser profile that had previously loaded the live reader. Verify the English Home and About labels, the PDF link, provisions 11-4, 12-3, 31-10, 35-16 and 56-6, and Appendices E and H. Test the same routes in a fresh profile and record the deployed commit and the results on the release issue.
