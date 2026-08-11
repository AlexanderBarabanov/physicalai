import { CapabilityCard } from "../../_components/CapabilityCard/CapabilityCard";
import { LeftToRightDottedConnector } from "../../_components/LeftToRightDottedConnector/LeftToRightDottedConnector";
import { RightToLeftDottedConnector } from "../../_components/RightToLeftDottedConnector/RightToLeftDottedConnector";
import { Section } from "../../_components/Section/Section";
import continuousLoopImg from "../../img/continuous-loop.png";
import styles from "./KeyCapabilities.module.css";
import { KeyHighlights } from "./KeyHighlights/KeyHighlights";
import { SupportedCameras } from "./SupportedCameras";
import { SupportedRobots } from "./SupportedRobots";

export const KeyCapabilities = () => {
  return (
    <Section>
      <h2 className={styles.title}>User Journey</h2>
      <p className={styles.description}>
        Physical AI Runtime provides the deployment-side components for running trained policies on
        real hardware. It handles camera capture, robot control, and policy inference with a unified
        API that works across different hardware vendors.
      </p>

      <div className={styles.twoColumnsFiveRowsGrid}>
        <div className={styles.row1}>
          <CapabilityCard
            title="Connect your camera"
            description="All cameras share a unified interface:connect(), read(), read_latest(), and context manager support. Switch hardware without changing application code."
            codeSnippet={`
            from physicalai.capture import UVCCamera, RealSenseCamera, read_cameras
            
            cameras = { 
              "wrist":UVCCamera(device="/dev/video0"), 
              "overhead":RealSenseCamera(serial_number="123456789")
            }
            
            for cam in cameras.values(): 
              cam.connect()

            synced =read_cameras(cameras)
            print(synced.frames["wrist"].data.shape)
            print(synced.frames["overhead"].data.shape)

            for cam in cameras.values(): 
              cam.disconnect()
          `}
          />

          <SupportedCameras />
        </div>

        <div className={styles.row2}>
          <LeftToRightDottedConnector />
        </div>

        <div className={styles.row3}>
          <SupportedRobots />

          <CapabilityCard
            className={styles.fullHeightCard}
            title="Connect your robots"
            description="Robots implement a Protocol-based interface. Any class with connect(), disconnect(), get_observation(), send_action(), and joint_names works - no inheritance required."
            codeSnippet={`
              from physicalai.robot import SO101
              robot = SO101(port="/dev/ttyUSB0")
              robot.connect()
            `}
          />
        </div>

        <div className={styles.row4}>
          <RightToLeftDottedConnector />
        </div>

        <div className={styles.row5}>
          <CapabilityCard
            title="Define your model"
            description={
              <>
                Load exported policies from{" "}
                <a
                  target="_blank"
                  style={{ color: "#00C7FD" }}
                  href="https://github.com/open-edge-platform/physical-ai-studio"
                  rel="noopener noreferrer"
                >
                  Physical AI Studio
                </a>
                . The InferenceModel class auto-detects the backend (OpenVINO or ONNX in this
                package; companion distributions may contribute additional adapters such as
                ExecuTorch) and handles action chunking automatically.
              </>
            }
            codeSnippet={`
              import numpy as np
              from physicalai.inference import InferenceModel
              model = InferenceModel("pi05-libero-fp16-ov", device="GPU")
            `}
          />

          <KeyHighlights />
        </div>

        <div className={styles.row6}>
          <LeftToRightDottedConnector />
        </div>

        <div className={styles.row7}>
          <img className={styles.continuousLoopImg} src={continuousLoopImg} alt="Continuous Loop" />

          <CapabilityCard
            title="Execution behavior"
            description="Connect all together. PolicyRuntime orchestrates the full control loop: connecting hardware, reading cameras, building observations, running inference, and dispatching actions to the robot."
            codeSnippet={`
              from physicalai.runtime import PolicyRuntime, SyncExecution
              from physicalai.inference import InferenceModel
              from physicalai.capture import UVCCamera, RealSenseCamera
              from physicalai.robot import SO101
              
              runtime = PolicyRuntime(
                  fps=30,
                  robot=SO101(port="/dev/ttyACM0"),
                  model=InferenceModel.load("./exports/act_policy"),
                  cameras={
                      "wrist": UVCCamera(device="/dev/video0", width=640, height=480),
                      "overhead": RealSenseCamera(serial_number="123456789"),
                  },
                  execution=SyncExecution(), # RTCExecution() or AsyncExecution()
              )

              with runtime:
                  runtime.run(duration_s=60)
            `}
          />
        </div>
      </div>
    </Section>
  );
};
