/* Sample "book" content pack — demonstrates that packs can add a whole new governing
   document (presbytery standing rules, session standing rules, church bylaws) alongside
   the four constitutional standards. Illustrative text only; not any actual presbytery's rules. */
window.BUNDLED_PACKS = (window.BUNDLED_PACKS || []).concat([{
  format: "pca-constitution-pack",
  version: 1,
  kind: "book",
  label: "Sample Presbytery Standing Rules",
  component: {
    key: "psr",
    abbr: "PSR",
    name: "Presbytery Standing Rules (Sample)",
    division: "local",
    mode: "paged",
    tag: "How a presbytery orders its own meetings and work, under the BCO.",
    lede: "Standing rules a presbytery adopts to govern its meetings, officers, and committees — subordinate to the Constitution and illustrative only in this sample.",
    meta: "Sample · 3 chapters · local rules under the BCO"
  },
  order: ["1", "2", "3"],
  chapters: {
    "1": {
      title: "Meetings",
      sections: [
        { ref: "1-1", body: "Stated meetings of Presbytery shall be held three times each year, in February, May, and September, at such places as Presbytery shall appoint. The Stated Clerk shall give notice of each stated meeting at least thirty days in advance." },
        { ref: "1-2", body: "Called meetings may be held on the request of any two ministers and two ruling elders of different churches, the call stating the particular business to be transacted, of which alone the called meeting may treat. Notice shall be given to every minister and every session at least ten days before the meeting." },
        { ref: "1-3", body: "A quorum shall consist of seven ministers and seven ruling elders representing at least five churches. Should a quorum fail to convene, the ministers and elders present may adjourn to a future day." },
        { ref: "1-4", body: "The order of the day for each stated meeting shall include worship, the report of the Stated Clerk, the examination and reception of candidates and ministers, and the reports of the standing committees, in that order, unless Presbytery by two-thirds vote determines otherwise." }
      ]
    },
    "2": {
      title: "Officers",
      sections: [
        { ref: "2-1", body: "The officers of Presbytery shall be a Moderator, a Stated Clerk, and a Treasurer. The Moderator shall be elected at the last stated meeting of each year and shall serve for the following year." },
        { ref: "2-2", body: "The Stated Clerk shall be elected for a term of three years and may be re-elected. He shall keep the rolls and minutes, conduct the correspondence of Presbytery, and have custody of its records and papers." },
        { ref: "2-3", body: "The Treasurer shall receive and disburse the funds of Presbytery as it shall direct, shall keep an accurate account, and shall report at each stated meeting. His accounts shall be audited annually." }
      ]
    },
    "3": {
      title: "Committees",
      sections: [
        { ref: "3-1", body: "There shall be standing committees on Candidates and Credentials, on Ministerial Care, and on Missions. Members shall be nominated by a Committee on Nominations and elected by Presbytery for staggered three-year terms." },
        { ref: "3-2", body: "The Committee on Candidates and Credentials shall supervise the care of those under the care of Presbytery, conduct preliminary examinations, and present its recommendations to Presbytery for action." },
        { ref: "3-3", body: "No committee shall take final action reserved to Presbytery itself; committees prepare and recommend, and Presbytery disposes. Each committee shall keep minutes and report in writing at each stated meeting." }
      ]
    }
  }
}]);
