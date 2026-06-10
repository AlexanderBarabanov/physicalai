import { CapabilityCard } from "../../_components/CapabilityCard/CapabilityCard";
import { Section } from "../../_components/Section/Section";
import styles from "./KeyCapabilities.module.css";

export const KeyCapabilities = () => {
  return (
    <Section>
      <h2 className={styles.title}>Key Capabilities</h2>

      <div className={styles.cards}>
        <CapabilityCard
          title="Continuous AI Execution"
          codeSnippet={`
            model = InferenceModel.load("./exports/act_policy")
            runtime = PolicyRuntime(robot=robot, model=model, fps=30)
            runtime.run(duration_s=60)`}
          description="Run AI policies as ongoing processes, not isolated calls - ideal for robotics and automation."
        />

        <CapabilityCard
          title="Asynchronous Runtime Architecture"
          codeSnippet={`
            runtime = PolicyRuntime(
              robot=robot,
              model=model,
              execution=SyncExecution(mode="chunk"),`}
          description={
            <>
              Handle multiple inputs and actions in parallel:
              <ul>
                <li>sensor streams</li>
                <li>model inference </li>
                <li>control signals</li>
              </ul>
              Without blocking execution.
            </>
          }
        />

        <CapabilityCard
          title="Unified Inference API"
          codeSnippet={`
            from physicalai import InferenceModel

            policy = InferenceModel("./exports/act_policy")
            action = policy(observation)`}
          description={
            <>
              Load and execute models consistently, regardless of origin:
              <ul>
                <li>trained policies</li>
                <li>external frameworks </li>
                <li>custom pipelines</li>
              </ul>
            </>
          }
        />

        <CapabilityCard
          title="Hardware Integration Layer"
          codeSnippet={`
            from physicalai.robot.so101 import SO101

            robot = SO101(port="/dev/ttyACM0")
            runtime = PolicyRuntime(robot=robot, model=model)`}
          description={
            <>
              Direct integration with:
              <ul>
                <li>cameras</li>
                <li>robots</li>
              </ul>
              Designed for clear separation between logic and hardware.
            </>
          }
        />

        <CapabilityCard
          title="CLI for Deployment & Operations"
          codeSnippet={`$ physicalai run policy.yaml`}
          description={
            <>
              Operate your system with simple commands:
              <ul>
                <li>run</li>
                <li>serve</li>
                <li>validate</li>
              </ul>
            </>
          }
        />

        <CapabilityCard
          title="Built-in Evaluation & Benchmarking"
          codeSnippet={`
            metrics = benchmark.run(policy, dataset)
            print(metrics["latency"], metrics["success_rate"])
          `}
          description={
            <>
              Measure performance of real-world execution:
              <ul>
                <li>latency</li>
                <li>stability</li>
                <li>repeatability</li>
              </ul>
            </>
          }
        />
      </div>
    </Section>
  );
};
