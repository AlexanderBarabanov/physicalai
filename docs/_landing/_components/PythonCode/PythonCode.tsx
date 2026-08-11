import { Code } from "@site/src/components/Code/Code";
import styles from "./PythonCode.module.css";

type PythonCodeProps = {
  code: string;
};

export const PythonCode = ({ code }: PythonCodeProps) => {
  return (
    <Code
      theme={{
        colors: {
          "editor.background": "#0C1D42",
          "editor.foreground": "#FFFFFF",
        },
      }}
      className={styles.codeContainer}
      code={code}
    />
  );
};
