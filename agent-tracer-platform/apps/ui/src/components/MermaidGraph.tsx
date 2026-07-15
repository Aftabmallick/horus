import { useEffect, useRef } from 'react';
import mermaid from 'mermaid';

interface Span {
  span_id: string;
  parent_span_id: string | null;
  name: string;
  span_type: string;
  status: string;
}

interface MermaidGraphProps {
  spans: Span[];
}

export function MermaidGraph({ spans }: MermaidGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    mermaid.initialize({
      startOnLoad: false,
      theme: 'dark',
      securityLevel: 'loose',
    });

    if (spans.length === 0) return;

    let chart = 'graph TD\n';
    
    // Add nodes
    spans.forEach(span => {
      const sanitizedName = span.name.replace(/[^a-zA-Z0-9 ]/g, '');
      const shape = span.span_type === 'AGENT' ? `{{"${sanitizedName}"}}` : 
                   span.span_type === 'LLM' ? `("${sanitizedName}")` : 
                   `["${sanitizedName}"]`;
                   
      chart += `  ${span.span_id}${shape}\n`;
      
      // Style errors
      if (span.status === 'ERROR') {
        chart += `  style ${span.span_id} stroke:#ef4444,stroke-width:2px\n`;
      }
    });

    // Add edges
    spans.forEach(span => {
      if (span.parent_span_id) {
        chart += `  ${span.parent_span_id} --> ${span.span_id}\n`;
      }
    });

    // Render logic
    const renderChart = async () => {
      if (containerRef.current) {
        try {
          const { svg } = await mermaid.render('mermaid-chart-' + Date.now(), chart);
          containerRef.current.innerHTML = svg;
        } catch (error) {
          console.error("Mermaid syntax error:", error);
          containerRef.current.innerHTML = "<div style='color:red;'>Failed to render graph.</div>";
        }
      }
    };

    renderChart();
  }, [spans]);

  return (
    <div 
      className="glass-panel animate-in" 
      style={{ height: '100%', width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'auto', padding: 24 }}
    >
      <div ref={containerRef} />
    </div>
  );
}
