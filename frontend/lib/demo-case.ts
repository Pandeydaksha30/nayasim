/**
 * Demo case used until the API exists. Every name, project, registration number and
 * order reference below is fictional and marked DEMO so it can never be mistaken for a
 * real citation.
 */
import type { Payment } from "./types";

export type Confidence = "high" | "review";

export interface Fact {
  id: string;
  label: string;
  value: string;
  docId: string;
  page: number;
  confidence: Confidence;
  note?: string;
}

export interface DocPage {
  number: number;
  /** Paragraphs. A fact's source span is written as {{factId|text}}. */
  paragraphs: string[];
}

export interface CaseDocument {
  id: string;
  title: string;
  kind: "Agreement" | "Allotment letter" | "Receipt" | "Builder letter";
  date: string;
  pages: number;
  language: "English" | "Hindi" | "English + Hindi";
  ocr: "Text layer" | "OCR" | "OCR, needs review";
  excerpt: DocPage[];
}

export interface GapQuestion {
  id: string;
  question: string;
  why: string;
  options: string[];
  answer?: string;
}

export type Speaker = "buyer" | "builder" | "judge";

export interface Citation {
  orderId: string;
  pinpoint: string;
  status: "verified" | "blocked";
}

export interface Argument {
  id: string;
  round: number;
  speaker: Speaker;
  heading: string;
  body: string;
  citations: Citation[];
}

export interface SimilarOrder {
  id: string;
  decided: string;
  bench: string;
  similarity: number;
  claim: string;
  outcome: "Allowed" | "Partly allowed" | "Dismissed";
  award: string;
  holding: string;
}

export interface HistoryEvent {
  date: string;
  text: string;
}

export interface CaseFile {
  id: string;
  title: string;
  buyer: string;
  builder: string;
  project: string;
  location: string;
  reraNo: string;
  unit: string;
  claimType: "Delayed possession" | "Refund";
  status: string;
  updated: string;
  price: number;
  possessionPromised: string;
  extensionMonths: number;
  extensionBasis: string;
  ratePct: number;
  rateBasis: string;
  asOf: string;
  payments: Payment[];
  documents: CaseDocument[];
  facts: Fact[];
  questions: GapQuestion[];
  hearing: Argument[];
  blockedCount: number;
  report: {
    similarCount: number;
    outcome: { allowed: number; partly: number; dismissed: number };
    band: [number, number];
    weakPoints: { title: string; detail: string; fix: string }[];
    defences: { title: string; seenIn: number; answer: string }[];
  };
  similar: SimilarOrder[];
  history: HistoryEvent[];
}

export const demoCase: CaseFile = {
  id: "demo",
  title: "Mehra v. Arvant Infra",
  buyer: "Ananya Mehra",
  builder: "Arvant Infra Pvt. Ltd.",
  project: "Skyline Residency, Tower C",
  location: "Sector 150, Greater Noida",
  reraNo: "UPRERAPRJ-DEMO-0417",
  unit: "C-1204, 1,450 sq ft",
  claimType: "Delayed possession",
  status: "Report ready",
  updated: "2026-11-06",
  price: 7_200_000,
  possessionPromised: "2021-06-30",
  extensionMonths: 6,
  extensionBasis: "UP RERA COVID-19 extension for projects due after 25 Mar 2020. Confirm the order in force for this project.",
  ratePct: 10.85,
  rateBasis: "UP RERA Rules r.15: SBI highest MCLR + 1%. Illustrative figure; check SBI's current MCLR before filing.",
  asOf: "2026-11-07",
  payments: [
    { id: "p1", date: "2018-03-12", amount: 720_000, reference: "Receipt AR/0912 (booking)" },
    { id: "p2", date: "2018-05-10", amount: 1_440_000, reference: "Receipt AR/1187 (allotment)" },
    { id: "p3", date: "2019-01-18", amount: 1_080_000, reference: "Receipt AR/2034 (foundation)" },
    { id: "p4", date: "2019-09-02", amount: 1_080_000, reference: "Receipt AR/2671 (5th floor slab)" },
    { id: "p5", date: "2020-08-14", amount: 720_000, reference: "Receipt AR/3320 (12th floor slab)" },
    { id: "p6", date: "2021-11-20", amount: 720_000, reference: "Receipt AR/4105 (superstructure)" },
  ],
  documents: [
    {
      id: "bba",
      title: "Builder-buyer agreement",
      kind: "Agreement",
      date: "2018-05-02",
      pages: 38,
      language: "English",
      ocr: "Text layer",
      excerpt: [
        {
          number: 4,
          paragraphs: [
            "AGREEMENT FOR SALE made at Greater Noida on {{f-agreement-date|2nd May 2018}} between {{f-builder|Arvant Infra Private Limited}}, a company incorporated under the Companies Act, 2013 (the “Promoter”), and {{f-buyer|Ms. Ananya Mehra}} (the “Allottee”).",
            "WHEREAS the Promoter is developing the project known as Skyline Residency, registered with the Uttar Pradesh Real Estate Regulatory Authority under registration number {{f-rera|UPRERAPRJ-DEMO-0417}}.",
            "1.1 Subject to the terms of this Agreement, the Promoter agrees to sell and the Allottee agrees to purchase Apartment No. {{f-unit|C-1204 on the twelfth floor of Tower C, having a carpet area of 1,450 square feet}}.",
            "1.2 The Total Price of the Apartment is {{f-price|Rs. 72,00,000/- (Rupees Seventy-Two Lakh only)}}, payable as per the construction-linked plan in Schedule C.",
          ],
        },
        {
          number: 17,
          paragraphs: [
            "7. POSSESSION OF THE APARTMENT",
            "7.1 The Promoter shall hand over possession of the Apartment to the Allottee on or before {{f-possession|30th June 2021}}, unless there is delay due to force majeure as defined in clause 9.",
            "7.2 If the Promoter fails to hand over possession by the date in clause 7.1, {{f-delay-clause|the Promoter shall pay the Allottee compensation at Rs. 5/- per square foot of carpet area per month}} for the period of delay.",
            "7.3 The Allottee shall take possession within two months of the written offer of possession, failing which holding charges shall apply.",
          ],
        },
      ],
    },
    {
      id: "allot",
      title: "Allotment letter",
      kind: "Allotment letter",
      date: "2018-04-18",
      pages: 2,
      language: "English",
      ocr: "OCR",
      excerpt: [
        {
          number: 1,
          paragraphs: [
            "Dear Ms. Mehra,",
            "We are pleased to allot you Apartment C-1204 in Skyline Residency against your application dated {{f-booking|12 March 2018}}. Your booking amount of Rs. 7,20,000/- is acknowledged.",
            "Construction-linked plan: 10% on booking, 20% on allotment, 15% on foundation, 15% on 5th floor slab, 10% on 12th floor slab, 10% on superstructure, 20% on offer of possession.",
          ],
        },
      ],
    },
    {
      id: "receipts",
      title: "Payment receipts (6)",
      kind: "Receipt",
      date: "2021-11-20",
      pages: 6,
      language: "English",
      ocr: "OCR, needs review",
      excerpt: [
        {
          number: 6,
          paragraphs: [
            "RECEIPT No. AR/4105",
            "Received with thanks from Ms. Ananya Mehra the sum of Rs. 7,20,000/- by RTGS dated {{f-last-payment|20-11-2021}} towards the superstructure instalment for Apartment C-1204.",
            "{{f-total-paid|Total received to date: Rs. 57,60,000/-}}",
          ],
        },
      ],
    },
    {
      id: "letter",
      title: "Builder letter on revised completion",
      kind: "Builder letter",
      date: "2024-02-10",
      pages: 1,
      language: "English + Hindi",
      ocr: "OCR",
      excerpt: [
        {
          number: 1,
          paragraphs: [
            "Sub: Revised completion schedule, Skyline Residency Tower C",
            "Owing to circumstances beyond our control, including the NGT construction bans and labour shortages, {{f-revised-date|the revised completion date for Tower C is 31 December 2025}}.",
            "{{f-escalation|Allottees are requested to pay a cost escalation charge of 2% of the Total Price}} before the offer of possession.",
          ],
        },
      ],
    },
  ],
  facts: [
    { id: "f-buyer", label: "Allottee", value: "Ananya Mehra", docId: "bba", page: 4, confidence: "high" },
    { id: "f-builder", label: "Promoter", value: "Arvant Infra Pvt. Ltd.", docId: "bba", page: 4, confidence: "high" },
    { id: "f-rera", label: "Project registration", value: "UPRERAPRJ-DEMO-0417", docId: "bba", page: 4, confidence: "high" },
    { id: "f-unit", label: "Unit", value: "C-1204, Tower C, 1,450 sq ft carpet", docId: "bba", page: 4, confidence: "high" },
    { id: "f-agreement-date", label: "Agreement date", value: "2 May 2018", docId: "bba", page: 4, confidence: "high" },
    { id: "f-booking", label: "Booking date", value: "12 Mar 2018", docId: "allot", page: 1, confidence: "high" },
    { id: "f-price", label: "Total price", value: "₹72,00,000", docId: "bba", page: 4, confidence: "high" },
    { id: "f-possession", label: "Promised possession", value: "30 Jun 2021", docId: "bba", page: 17, confidence: "high" },
    {
      id: "f-delay-clause",
      label: "Delay clause",
      value: "₹5 per sq ft per month",
      docId: "bba",
      page: 17,
      confidence: "high",
      note: "One-sided compensation clauses are often not enforced over the statutory rate. The calculator uses the statutory rate.",
    },
    {
      id: "f-total-paid",
      label: "Total paid",
      value: "₹57,60,000",
      docId: "receipts",
      page: 6,
      confidence: "review",
      note: "Read by OCR from a scanned receipt. Matches the sum of the six receipts.",
    },
    { id: "f-last-payment", label: "Last payment", value: "20 Nov 2021", docId: "receipts", page: 6, confidence: "review", note: "Date format on the scan is ambiguous (dd-mm-yyyy assumed)." },
    { id: "f-revised-date", label: "Builder's revised date", value: "31 Dec 2025", docId: "letter", page: 1, confidence: "high" },
    { id: "f-escalation", label: "Escalation demand", value: "2% of price (₹1,44,000)", docId: "letter", page: 1, confidence: "high" },
  ],
  questions: [
    {
      id: "q-offer",
      question: "Have you received a written offer of possession for C-1204?",
      why: "If an offer was made, delay interest usually stops at that date, not today.",
      options: ["No", "Yes, with an occupancy certificate", "Yes, without an occupancy certificate"],
      answer: "No",
    },
    {
      id: "q-missed",
      question: "Did you miss or pay late any instalment demanded by the builder?",
      why: "Builders often argue the buyer defaulted first. Late payments can reduce the award.",
      options: ["No, all paid on time", "Yes, one or more were late", "Not sure"],
    },
    {
      id: "q-relief",
      question: "Do you want to keep the flat, or withdraw and take a refund?",
      why: "This picks the relief under section 18: interest for every month of delay, or a refund of everything paid, with interest.",
      options: ["Keep the flat and claim delay interest", "Withdraw and claim a refund", "Undecided: show both"],
      answer: "Undecided: show both",
    },
    {
      id: "q-escalation",
      question: "Have you paid the 2% escalation charge demanded in the February 2024 letter?",
      why: "Paying without protest can be read as accepting the revised date.",
      options: ["No", "Yes, under protest in writing", "Yes, without protest"],
    },
  ],
  hearing: [
    {
      id: "a1",
      round: 1,
      speaker: "buyer",
      heading: "Possession is more than five years overdue",
      body: "Clause 7.1 fixes possession on or before 30 June 2021. Even after a six-month COVID extension the due date is 30 December 2021. No offer of possession has been made. The allottee has paid ₹57.6 lakh, 80% of the price, and is entitled to interest for every month of delay under section 18(1).",
      citations: [
        { orderId: "DEMO/GBN/2023/0112", pinpoint: "para 14", status: "verified" },
        { orderId: "DEMO/GBN/2024/0458", pinpoint: "para 9", status: "verified" },
      ],
    },
    {
      id: "a2",
      round: 1,
      speaker: "builder",
      heading: "Delay was caused by force majeure",
      body: "Construction was stopped by NGT and pollution-control bans in the NCR in 2019 to 2021, and by COVID-19 lockdowns. Clause 9 excludes these periods from the delay. The 2024 letter informed the allottee of the revised date, and the project is now registered with an extended completion date.",
      citations: [
        { orderId: "DEMO/GBN/2022/0871", pinpoint: "para 11", status: "verified" },
        { orderId: "DEMO/GBN/2021/1930", pinpoint: "para 6", status: "blocked" },
      ],
    },
    {
      id: "a3",
      round: 2,
      speaker: "buyer",
      heading: "Bans were short and are already covered by the extension",
      body: "Construction bans in the NCR ran for weeks, not years. The COVID extension already covers the lockdown period. A revised date stated unilaterally by the promoter does not change the date agreed with the allottee.",
      citations: [{ orderId: "DEMO/GBN/2024/0458", pinpoint: "para 12", status: "verified" }],
    },
    {
      id: "a4",
      round: 2,
      speaker: "builder",
      heading: "The allottee accepted delays by continuing to pay",
      body: "The allottee paid the superstructure instalment in November 2021, after the original date had passed, without objection. This shows acceptance of the revised schedule.",
      citations: [{ orderId: "DEMO/GBN/2023/0377", pinpoint: "para 8", status: "verified" }],
    },
    {
      id: "a5",
      round: 3,
      speaker: "judge",
      heading: "Reasoned view",
      body: "The agreed date stands at 30 June 2021, extended by six months under the COVID order. The promoter has not shown that construction bans after that date caused delay of the length claimed. Paying a demanded instalment is not, on its own, acceptance of a new date. The allottee is entitled to interest at the prescribed rate on each payment from the due date until a valid offer of possession with an occupancy certificate. The 2% escalation charge has no basis in the agreement.",
      citations: [
        { orderId: "DEMO/GBN/2023/0112", pinpoint: "para 14", status: "verified" },
        { orderId: "DEMO/GBN/2024/0458", pinpoint: "para 12", status: "verified" },
        { orderId: "DEMO/GBN/2023/0377", pinpoint: "para 10", status: "verified" },
      ],
    },
  ],
  blockedCount: 1,
  report: {
    similarCount: 148,
    outcome: { allowed: 0.64, partly: 0.25, dismissed: 0.11 },
    band: [0.55, 0.72],
    weakPoints: [
      {
        title: "Payment after the due date, without protest",
        detail: "You paid ₹7.2 lakh in November 2021, after possession was due. Builders cite this as acceptance of delay; it worked for them in 9 of the 41 similar orders where it was raised.",
        fix: "Attach any email or message from that time showing you objected to the delay. If there is none, say in the complaint that payment was made to avoid cancellation and forfeiture.",
      },
      {
        title: "Two receipts are low-quality scans",
        detail: "Receipts AR/3320 and AR/4105 were read by OCR and could not be fully checked. Unclear payment proof is a common reason for a reduced award.",
        fix: "Get the bank statement entries for 14 Aug 2020 and 20 Nov 2021 and add them as annexures.",
      },
      {
        title: "No written demand for possession",
        detail: "There is no letter from you asking for possession or objecting to the revised 2025 date. Authorities give weight to a buyer who raised the issue early.",
        fix: "Send a short written notice to the builder before filing and include the proof of dispatch.",
      },
    ],
    defences: [
      { title: "Force majeure: NGT bans, COVID-19, labour shortage", seenIn: 0.82, answer: "Covered by the six-month extension; bans were short; no proof of the length of delay." },
      { title: "Buyer accepted the delay by continuing to pay", seenIn: 0.28, answer: "Payment under a construction-linked demand is not acceptance; pay under protest from now on." },
      { title: "Agreement caps compensation at ₹5 per sq ft per month", seenIn: 0.61, answer: "One-sided clause; the statutory rate applies under section 18." },
      { title: "Project is registered with a later completion date", seenIn: 0.47, answer: "Registration dates bind the regulator's timeline, not the date agreed with the buyer." },
    ],
  },
  similar: [
    {
      id: "DEMO/GBN/2023/0112",
      decided: "2023-08-21",
      bench: "Bench II, Greater Noida",
      similarity: 0.91,
      claim: "Delayed possession, 4 yrs, construction-linked plan",
      outcome: "Allowed",
      award: "Interest at prescribed rate from due date to offer of possession",
      holding: "Force majeure plea rejected where no evidence linked bans to the length of delay.",
    },
    {
      id: "DEMO/GBN/2024/0458",
      decided: "2024-03-04",
      bench: "Bench I, Greater Noida",
      similarity: 0.88,
      claim: "Delayed possession, revised date given by promoter",
      outcome: "Allowed",
      award: "Interest on each payment; escalation demand quashed",
      holding: "A unilateral revised completion date does not alter the agreed possession date.",
    },
    {
      id: "DEMO/GBN/2023/0377",
      decided: "2023-05-17",
      bench: "Bench II, Greater Noida",
      similarity: 0.84,
      claim: "Delayed possession, payment made after due date",
      outcome: "Partly allowed",
      award: "Interest from extended due date; holding charges set aside",
      holding: "Paying a demanded instalment after the due date is not, by itself, acceptance of delay.",
    },
    {
      id: "DEMO/GBN/2022/0871",
      decided: "2022-11-09",
      bench: "Bench III, Greater Noida",
      similarity: 0.79,
      claim: "Delayed possession, COVID-19 period",
      outcome: "Partly allowed",
      award: "Interest after excluding the COVID-19 extension period",
      holding: "COVID-19 extension excluded from delay; remaining delay compensated.",
    },
    {
      id: "DEMO/NOI/2024/0213",
      decided: "2024-09-26",
      bench: "Bench I, Noida",
      similarity: 0.74,
      claim: "Delayed possession, buyer missed two instalments",
      outcome: "Dismissed",
      award: "None",
      holding: "Allottee's own default in payment disentitled interest for the overlapping period.",
    },
  ],
  history: [
    { date: "2026-11-06", text: "Report generated from 148 similar orders decided up to 31 Oct 2026." },
    { date: "2026-11-06", text: "Simulated hearing run: 3 rounds, 1 argument removed by the citation check." },
    { date: "2026-11-05", text: "Answered 2 of 4 follow-up questions." },
    { date: "2026-11-05", text: "13 facts extracted; 2 marked for review." },
    { date: "2026-11-05", text: "4 documents uploaded (47 pages)." },
  ],
};

export function getCase(id: string): CaseFile | undefined {
  return id === demoCase.id ? demoCase : undefined;
}
