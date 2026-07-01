import openVinoIr from "../../../img/openvino-ir.png";
import styles from "./KeyHighlights.module.css";

export const KeyHighlights = () => {
  return (
    <div>
      <img src={openVinoIr} alt="OpenVINO IR" />

      <h3 className={styles.title}>Key highlights</h3>

      <ul className={styles.list}>
        <li>Backend-agnostic (OV is one of backends)</li>
        <li>Configurable via manifest file</li>
        <li>
          Allows utilizing custom pre/post processing nodes (for instance,
          tokenization with OV tokenizers)
        </li>
        <li>Customizable model execution flow</li>
      </ul>
    </div>
  );
};
