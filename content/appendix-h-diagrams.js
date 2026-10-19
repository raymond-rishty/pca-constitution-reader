/* Appendix H flowcharts as a bundled multilingual book pack. */
window.BUNDLED_PACKS = window.BUNDLED_PACKS || [];
window.BUNDLED_PACKS.push({
  format: "pca-constitution-pack",
  version: 1,
  kind: "book",
  label: "Appendix H Flowcharts",
  notice: "Appendix H flowcharts · English, Spanish, and Korean",
  component: {
    key: "appendix-h-charts",
    abbr: "App H",
    name: "Appendix H Flowcharts",
    division: "supplemental",
    icon: "book",
    tag: "Suggested appellate court procedures in three languages.",
    lede: "Flowcharts accompanying Appendix H of the PCA Book of Church Order and its Spanish and Korean editions.",
    meta: "English · Spanish · Korean"
  },
  order: ["en", "es", "ko"],
  chapters: {
    en: {
      title: "English",
      sections: [{
        ref: "EN",
        prose: true,
        body: '<img class="pack-figure" src="diagrams/appendix-h.svg" alt="Appendix H flowchart: Presbytery appellate court procedures">'
      }]
    },
    es: {
      title: "Español",
      sections: [{
        ref: "ES",
        prose: true,
        body: '<img class="pack-figure" src="diagrams/appendix-h.es.svg" alt="Diagrama del Apéndice H: procedimientos de los tribunales de apelación del presbiterio">'
      }]
    },
    ko: {
      title: "한국어",
      sections: [{
        ref: "KO",
        prose: true,
        body: '<img class="pack-figure" src="diagrams/appendix-h.ko.svg" alt="부록 H: 노회 상소 치리회 절차 흐름도">'
      }]
    }
  }
});
