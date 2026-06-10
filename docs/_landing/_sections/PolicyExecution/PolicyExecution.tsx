import { PolicyCard } from "../../_components/PolicyCard/PolicyCard";
import { Section } from "../../_components/Section/Section";
import styles from "./PolicyExecution.module.css";

export const PolicyExecution = () => (
  <Section className={styles.container}>
    <h2 className={styles.title}>Real-time Policy Execution Engine</h2>

    <p className={styles.description}>
      At the heart of the framework is a policy runtime designed for physical
      systems:
    </p>

    <ul className={styles.list}>
      <li>Executes AI policies continuously, not as one-off predictions</li>
      <li>Supports asynchronous, multi-threaded workloads</li>
      <li>Built for environments where timing and coordination matter</li>
    </ul>

    <h2 className={styles.title}>Why it matters</h2>

    <div className={styles.cardsContainer}>
      <PolicyCard
        title={"Traditional AI pipelines"}
        listItems={["batch-based", "stateless", "disconnected from execution"]}
      />
      <PolicyCard
        title={"Physical AI Runtime"}
        listItems={[
          "event-driven",
          "long-running",
          "connected to sensors and actuators",
        ]}
      />
      <PolicyCard
        title={"This enables systems that"}
        listItems={[
          "react in real time",
          "coordinate multiple inputs",
          "operate reliably under changing conditions",
        ]}
      />
    </div>
  </Section>
);
