import { ReactNode } from "react";
import { DottedCard } from "../DottedCard/DottedCardDetails";
import { PythonCode } from "../PythonCode/PythonCode";
import styles from "./CapabilityCard.module.css";

type CapabilityCardProps = {
  title: string;
  description: ReactNode;
  codeSnippet: string;
};

export const CapabilityCard = ({
  title,
  description,
  codeSnippet,
}: CapabilityCardProps) => {
  return (
    <DottedCard>
      <h3 className={styles.title}>{title}</h3>

      <div className={styles.description}>{description}</div>

      <PythonCode code={codeSnippet} />
    </DottedCard>
  );
};
