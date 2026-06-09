import Heading from "@theme/Heading";

import { Section } from "../../_components/Section/Section";
import styles from "./HeroSection.module.css";

export const HeroSection = () => (
  <Section>
    <Heading as="h1" className={styles.sectionTitle}>
      Run AI in the real world
    </Heading>

    <h2>Reliably, in real time</h2>

    <p>
      Physical AI Framework is a production-ready runtime that executes AI
      policies on physical systems - combining real-time inference, flexible
      execution modes, and hardware integration in one unified platform.
    </p>

    <div>Cards</div>

    <h3>Get Started Today</h3>
    <h4>From code to action</h4>

    <div>
      <div>blue gradiend card</div>
      <div>how it works illustration</div>
    </div>
  </Section>
);
