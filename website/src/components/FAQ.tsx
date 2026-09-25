import Accordion from "@mui/material/Accordion";
import AccordionDetails from "@mui/material/AccordionDetails";
import AccordionSummary from "@mui/material/AccordionSummary";
import { LuChevronDown } from "react-icons/lu";
import { faqs } from "../data/site";
import { Reveal } from "./Reveal";

export function FAQ() {
  return (
    <section id="faq" className="px-4 py-12">
      <div className="mx-auto max-w-3xl">
        <Reveal>
          <p className="text-sm tracking-wide text-muted uppercase">05 · FAQ</p>
          <h2 className="font-display mt-3 text-4xl">Questions operators actually ask.</h2>
        </Reveal>
        <div className="mt-10">
          {faqs.map((item, index) => (
            <Accordion key={item.q} defaultExpanded={index === 0} disableGutters>
              <AccordionSummary expandIcon={<LuChevronDown />}>
                {item.q}
              </AccordionSummary>
              <AccordionDetails>{item.a}</AccordionDetails>
            </Accordion>
          ))}
        </div>
      </div>
    </section>
  );
}
