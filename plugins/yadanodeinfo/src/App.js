import React, { useCallback, useEffect, useState } from "react";
import "./App.css";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";

function App() {
  const [txnData, setTxnData] = useState(null);
  const [blockData, setBlockData] = useState(null);
  const [nonceData, setNonceData] = useState(null);
  const [peerData, setPeerData] = useState(null);
  const [heightData, setHeightData] = useState(null);
  const [messageSenderData, setMessageSenderData] = useState(null);
  const [slowQueryData, setSlowQueryData] = useState(null);
  const [dockerPythonData, setDockerPythonData] = useState(null);
  const [dockerMongodbData, setDockerMongodbData] = useState(null);
  const [sampleSize, setSampleSize] = useState(10000000);
  const [url, setUrl] = useState(window.location.origin);
  const [archived, setArchived] = useState(false);
  const resetData = useCallback(async (sampleSize, url, archived) => {
    const arch = archived ? "&archived=true" : "";

    const raw_data = await (
      await fetch(`${url}/get-status?from_time=${sampleSize}${arch}`)
    ).json();
    const txn_queue = raw_data.map((item) => {
      return item.processing_queues.TransactionProcessingQueue;
    });
    setTxnData(txn_queue);
    const block_queue = raw_data.map((item) => {
      return item.processing_queues.BlockProcessingQueue;
    });
    setBlockData(block_queue);
    const nonce_queue = raw_data.map((item) => {
      return item.processing_queues.NonceProcessingQueue;
    });
    setNonceData(nonce_queue);
    const peer_data = raw_data.map((item) => {
      return {
        inbound_peers: item.inbound_peers,
        inbound_pending: item.inbound_pending,
        outbound_peers: item.outbound_peers,
        outbound_ignore: item.outbound_ignore,
        outbound_pending: item.outbound_pending,
      };
    });
    setPeerData(peer_data);
    const height_data = raw_data.map((item) => {
      return {
        height: item.height,
      };
    });
    setHeightData(height_data);
    const message_sender_data = raw_data.map((item) => {
      return {
        nodeServer: item.message_sender.nodeServer.num_messages,
        nodClient: item.message_sender.nodeClient.num_messages,
      };
    });
    setMessageSenderData(message_sender_data);
    const slow_query_data = raw_data.map((item) => {
      return {
        count: item.slow_queries.count,
      };
    });
    setSlowQueryData(slow_query_data);
    if (raw_data[0] && !raw_data[0].docker) return;
    const docker_python_data = raw_data.map((item) => {
      return {
        cpu_percent: item.docker["yadacoin_yada-node_1"].cpu_percent,
        mem_percent: item.docker["yadacoin_yada-node_1"].mem_percent,
      };
    });
    setDockerPythonData(docker_python_data);
    const docker_mongodb_data = raw_data.map((item) => {
      return {
        cpu_percent: item.docker["yadacoin_mongodb_1"].cpu_percent,
        mem_percent: item.docker["yadacoin_mongodb_1"].mem_percent,
      };
    });
    setDockerMongodbData(docker_mongodb_data);
  }, []);
  useEffect(() => {
    (async () => {
      if (txnData) return;
      await resetData(sampleSize, url, archived);
      setInterval(async () => {
        await resetData(sampleSize, url, archived);
      }, 10000);
    })();
  }, [resetData, txnData, sampleSize, url]);

  const chartProps = {
    width: 420,
    height: 280,
  };

  const axisStyle = {
    stroke: "#8b949e",
    tick: { fill: "#8b949e", fontSize: 11 },
  };
  const gridStyle = { stroke: "#30363d" };

  return (
    <div className="App">
      <header className="app-header">
        <svg
          width="40"
          height="40"
          viewBox="0 0 40 40"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <rect width="40" height="40" rx="10" fill="#1a2332" />
          <text
            x="20"
            y="27"
            fontSize="18"
            fontFamily="sans-serif"
            fontWeight="bold"
            fill="#58a6ff"
            textAnchor="middle"
          >
            Y
          </text>
        </svg>
        <div>
          <h1>Node Info</h1>
          <p>Live status metrics from /get-status</p>
        </div>
      </header>

      <main className="app-main">
        <div className="controls">
          <label>
            Node URL
            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.currentTarget.value)}
            />
          </label>
          <label>
            Sample size (ms)
            <input
              type="number"
              value={sampleSize}
              onChange={(e) => setSampleSize(e.currentTarget.value)}
            />
          </label>
          <label>
            <input
              type="checkbox"
              checked={archived}
              onChange={(e) => setArchived(e.currentTarget.checked)}
            />
            Archived
          </label>
          <button onClick={() => resetData(sampleSize, url, archived)}>
            Go
          </button>
        </div>

        <div className="section-label">Processing Queues</div>
        <div className="charts-grid">
          <div className="chart-card">
            <h2>Transaction Processing Queue</h2>
            <LineChart {...chartProps} data={txnData}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridStyle.stroke} />
              <XAxis dataKey="time" {...axisStyle} />
              <YAxis {...axisStyle} />
              <Tooltip
                contentStyle={{
                  background: "#161b22",
                  border: "1px solid #30363d",
                  color: "#c9d1d9",
                }}
              />
              <Legend wrapperStyle={{ fontSize: 12, color: "#8b949e" }} />
              <Line
                type="monotone"
                dataKey="average_processing_time"
                stroke="#58a6ff"
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="num_items_processed"
                stroke="#3fb950"
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="queue_item_count"
                stroke="#ffa657"
                dot={false}
              />
            </LineChart>
          </div>
          <div className="chart-card">
            <h2>Block Processing Queue</h2>
            <LineChart {...chartProps} data={blockData}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridStyle.stroke} />
              <XAxis dataKey="time" {...axisStyle} />
              <YAxis {...axisStyle} />
              <Tooltip
                contentStyle={{
                  background: "#161b22",
                  border: "1px solid #30363d",
                  color: "#c9d1d9",
                }}
              />
              <Legend wrapperStyle={{ fontSize: 12, color: "#8b949e" }} />
              <Line
                type="monotone"
                dataKey="average_processing_time"
                stroke="#58a6ff"
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="num_items_processed"
                stroke="#3fb950"
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="queue_item_count"
                stroke="#ffa657"
                dot={false}
              />
            </LineChart>
          </div>
          <div className="chart-card">
            <h2>Nonce Processing Queue</h2>
            <LineChart {...chartProps} data={nonceData}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridStyle.stroke} />
              <XAxis dataKey="time" {...axisStyle} />
              <YAxis {...axisStyle} />
              <Tooltip
                contentStyle={{
                  background: "#161b22",
                  border: "1px solid #30363d",
                  color: "#c9d1d9",
                }}
              />
              <Legend wrapperStyle={{ fontSize: 12, color: "#8b949e" }} />
              <Line
                type="monotone"
                dataKey="average_processing_time"
                stroke="#58a6ff"
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="num_items_processed"
                stroke="#3fb950"
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="queue_item_count"
                stroke="#ffa657"
                dot={false}
              />
            </LineChart>
          </div>
        </div>

        <div className="section-label">Network</div>
        <div className="charts-grid">
          <div className="chart-card">
            <h2>Peers</h2>
            <LineChart {...chartProps} data={peerData}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridStyle.stroke} />
              <XAxis dataKey="time" {...axisStyle} />
              <YAxis {...axisStyle} />
              <Tooltip
                contentStyle={{
                  background: "#161b22",
                  border: "1px solid #30363d",
                  color: "#c9d1d9",
                }}
              />
              <Legend wrapperStyle={{ fontSize: 12, color: "#8b949e" }} />
              <Line
                type="monotone"
                dataKey="inbound_peers"
                stroke="#58a6ff"
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="inbound_pending"
                stroke="#3fb950"
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="outbound_peers"
                stroke="#ffa657"
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="outbound_ignore"
                stroke="#f78166"
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="outbound_pending"
                stroke="#d2a8ff"
                dot={false}
              />
            </LineChart>
          </div>
          <div className="chart-card">
            <h2>Message Sender</h2>
            <LineChart {...chartProps} data={messageSenderData}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridStyle.stroke} />
              <XAxis dataKey="time" {...axisStyle} />
              <YAxis {...axisStyle} />
              <Tooltip
                contentStyle={{
                  background: "#161b22",
                  border: "1px solid #30363d",
                  color: "#c9d1d9",
                }}
              />
              <Legend wrapperStyle={{ fontSize: 12, color: "#8b949e" }} />
              <Line
                type="monotone"
                dataKey="nodeServer"
                stroke="#58a6ff"
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="nodClient"
                stroke="#3fb950"
                dot={false}
              />
            </LineChart>
          </div>
        </div>

        <div className="section-label">Chain</div>
        <div className="charts-grid">
          <div className="chart-card">
            <h2>Height</h2>
            <LineChart {...chartProps} data={heightData}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridStyle.stroke} />
              <XAxis dataKey="time" {...axisStyle} />
              <YAxis {...axisStyle} />
              <Tooltip
                contentStyle={{
                  background: "#161b22",
                  border: "1px solid #30363d",
                  color: "#c9d1d9",
                }}
              />
              <Legend wrapperStyle={{ fontSize: 12, color: "#8b949e" }} />
              <Line
                type="monotone"
                dataKey="height"
                stroke="#58a6ff"
                dot={false}
              />
            </LineChart>
          </div>
          <div className="chart-card">
            <h2>Slow Queries</h2>
            <LineChart {...chartProps} data={slowQueryData}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridStyle.stroke} />
              <XAxis dataKey="time" {...axisStyle} />
              <YAxis {...axisStyle} />
              <Tooltip
                contentStyle={{
                  background: "#161b22",
                  border: "1px solid #30363d",
                  color: "#c9d1d9",
                }}
              />
              <Legend wrapperStyle={{ fontSize: 12, color: "#8b949e" }} />
              <Line
                type="monotone"
                dataKey="count"
                stroke="#f78166"
                dot={false}
              />
            </LineChart>
          </div>
        </div>

        {(dockerPythonData || dockerMongodbData) && (
          <>
            <div className="section-label">Docker</div>
            <div className="charts-grid">
              {dockerPythonData && (
                <div className="chart-card">
                  <h2>Python Container</h2>
                  <LineChart {...chartProps} data={dockerPythonData}>
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke={gridStyle.stroke}
                    />
                    <XAxis dataKey="time" {...axisStyle} />
                    <YAxis {...axisStyle} />
                    <Tooltip
                      contentStyle={{
                        background: "#161b22",
                        border: "1px solid #30363d",
                        color: "#c9d1d9",
                      }}
                    />
                    <Legend wrapperStyle={{ fontSize: 12, color: "#8b949e" }} />
                    <Line
                      type="monotone"
                      dataKey="cpu_percent"
                      stroke="#58a6ff"
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="mem_percent"
                      stroke="#3fb950"
                      dot={false}
                    />
                  </LineChart>
                </div>
              )}
              {dockerMongodbData && (
                <div className="chart-card">
                  <h2>MongoDB Container</h2>
                  <LineChart {...chartProps} data={dockerMongodbData}>
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke={gridStyle.stroke}
                    />
                    <XAxis dataKey="time" {...axisStyle} />
                    <YAxis {...axisStyle} />
                    <Tooltip
                      contentStyle={{
                        background: "#161b22",
                        border: "1px solid #30363d",
                        color: "#c9d1d9",
                      }}
                    />
                    <Legend wrapperStyle={{ fontSize: 12, color: "#8b949e" }} />
                    <Line
                      type="monotone"
                      dataKey="cpu_percent"
                      stroke="#58a6ff"
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="mem_percent"
                      stroke="#3fb950"
                      dot={false}
                    />
                  </LineChart>
                </div>
              )}
            </div>
          </>
        )}
      </main>

      <footer className="app-footer">
        YadaCoin Node &mdash; <a href="/">← Back to Dashboard</a>
      </footer>
    </div>
  );
}

export default App;
