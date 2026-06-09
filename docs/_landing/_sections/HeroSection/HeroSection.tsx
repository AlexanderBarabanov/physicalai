import clsx from "clsx";

import { CardDetails } from "../../_components/CardDetails/CardDetails";
import { DottedCard } from "../../_components/DottedCard/DottedCardDetails";
import { PythonCode } from "../../_components/PythonCode/PythonCode";
import { Section } from "../../_components/Section/Section";
import continuousLoopImg from "../../img/continuous-loop.png";
import styles from "./HeroSection.module.css";

export const HeroSection = () => {
  return (
    <Section>
      <h1 className={clsx(styles.title, styles.gradientTitle)}>
        Run AI in the real world
      </h1>
      <h1 className={styles.title}>Reliably, in real time</h1>

      <p className={styles.description}>
        Physical AI Framework is a production-ready runtime that executes AI
        policies on physical systems - combining real-time inference, flexible
        execution modes, and hardware integration in one unified platform.
      </p>

      <div className={styles.cardsContainer}>
        <CardDetails
          iconUrl={""}
          title="Real-Time AI Execution"
          description="The framework enables reliable, real-time execution of AI policies on physical systems such as robots and edge devices."
        />

        <CardDetails
          iconUrl={""}
          title="Integration with Physical Hardware"
          description="It combines sync, async or remote execution and direct hardware integration into a unified platform for stable AI operation."
        />

        <CardDetails
          iconUrl={""}
          title="Dependable Physical Behavior"
          description="Physical AI emphasizes dependable behavior in dynamic environments, prioritizing timing, coordination, and safety over just prediction accuracy."
        />

        <CardDetails
          iconUrl={""}
          title="Beyond Model Serving"
          description="The framework serves as a runtime layer enabling AI deployment beyond labs into real-world production environments."
        />
      </div>

      <div className={styles.installContainer}>
        <h3>Get Started Today</h3>
        <h4>From code to action</h4>

        <div className={styles.installCards}>
          <DottedCard>
            <div>
              <p>Install</p>
              <PythonCode code={`pip install physicalai`} />
            </div>

            <div>
              <p>Inference (Python)</p>
              <PythonCode
                code={`from physicalai import InferenceModel
                        model =InferenceModel("./exported_policy")
                        action =model.select_action(observation)`}
              />
            </div>

            <div>
              <p>CLI</p>
              <PythonCode
                code={`physicalai run --model ./exports/act_policy --robot robot.yaml`}
              />
            </div>
          </DottedCard>

          <div className={styles.continuousLoop}>
            <img src={continuousLoopImg} alt="Description of image" />
          </div>
        </div>
      </div>
    </Section>
  );
};
