import ReactMarkdown from "react-markdown";

interface AnswerOverlayProps {
  visible: boolean;
  content: string;
  isStreaming: boolean;
}

export default function AnswerOverlay({
  visible,
  content,
  isStreaming,
}: AnswerOverlayProps) {
  if (!visible) return null;

  return (
    <div className="fixed top-24 left-1/2 -translate-x-1/2 z-40 w-[800px] max-h-[600px]">
      <div className="bg-overlay-bg backdrop-blur-md rounded-lg shadow-2xl border border-gray-800 overflow-hidden">
        <div className="p-6 overflow-y-auto max-h-[600px] custom-scrollbar">
          {content ? (
            <div className="prose prose-invert prose-sm max-w-none">
              <ReactMarkdown
                components={{
                  code({ node, inline, className, children, ...props }) {
                    return inline ? (
                      <code
                        className="bg-overlay-code px-1.5 py-0.5 rounded text-sm font-mono"
                        {...props}
                      >
                        {children}
                      </code>
                    ) : (
                      <pre className="bg-overlay-code p-4 rounded-lg overflow-x-auto">
                        <code className="text-sm font-mono" {...props}>
                          {children}
                        </code>
                      </pre>
                    );
                  },
                }}
              >
                {content}
              </ReactMarkdown>
              {isStreaming && (
                <span className="inline-block w-1 h-4 bg-green-500 animate-pulse ml-1" />
              )}
            </div>
          ) : (
            <div className="text-gray-400 text-center py-8">
              Waiting for response...
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
