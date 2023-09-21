import React, { useCallback, useEffect, useState } from "react";
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

  return (
    <div className="App">
      <input
        type="text"
        value={url}
        onChange={(e) => {
          setUrl(e.currentTarget.value);
        }}
      />
      <input
        type="number"
        value={sampleSize}
        onChange={(e) => {
          setSampleSize(e.currentTarget.value);
        }}
      />
      <input
        type="checkbox"
        value={archived}
        onChange={(e) => {
          setArchived(e.currentTarget.checked);
        }}
      />
      <button
        onClick={() => {
          resetData(sampleSize, url, archived);
        }}
      >
        Go
      </button>
      <div
        style={{
          display: "flex",
          flex: 1,
          flexDirection: "row",
          justifyContent: "left",
          flexWrap: "wrap",
        }}
      >
        <div>
          <h2>TransactionProcessingQueue</h2>
          <LineChart width={400} height={300} data={txnData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="time" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line
              type="monotone"
              dataKey="average_processing_time"
              stroke="#8884d8"
            />
            <Line
              type="monotone"
              dataKey="num_items_processed"
              stroke="#82ca9d"
            />
            <Line type="monotone" dataKey="queue_item_count" stroke="#ff7300" />
          </LineChart>
        </div>
        <div>
          <h2>BlockProcessingQueue</h2>
          <LineChart width={400} height={300} data={blockData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="time" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line
              type="monotone"
              dataKey="average_processing_time"
              stroke="#8884d8"
            />
            <Line
              type="monotone"
              dataKey="num_items_processed"
              stroke="#82ca9d"
            />
            <Line type="monotone" dataKey="queue_item_count" stroke="#ff7300" />
          </LineChart>
        </div>
        <div>
          <h2>NonceProcessingQueue</h2>
          <LineChart width={400} height={300} data={nonceData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="time" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line
              type="monotone"
              dataKey="average_processing_time"
              stroke="#8884d8"
            />
            <Line
              type="monotone"
              dataKey="num_items_processed"
              stroke="#82ca9d"
            />
            <Line type="monotone" dataKey="queue_item_count" stroke="#ff7300" />
          </LineChart>
        </div>
        <div>
          <h2>Peers</h2>
          <LineChart width={400} height={300} data={peerData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="time" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="inbound_peers" stroke="#8884d8" />
            <Line type="monotone" dataKey="inbound_pending" stroke="#82ca9d" />
            <Line type="monotone" dataKey="outbound_peers" stroke="#ff7300" />
            <Line type="monotone" dataKey="outbound_ignore" stroke="#ff3300" />
            <Line type="monotone" dataKey="outbound_pending" stroke="#ff7400" />
          </LineChart>
        </div>
        <div>
          <h2>Height</h2>
          <LineChart width={400} height={300} data={heightData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="time" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="height" stroke="#8884d8" />
          </LineChart>
        </div>
        <div>
          <h2>Message Sender</h2>
          <LineChart width={400} height={300} data={messageSenderData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="time" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="nodeServer" stroke="#8884d8" />
            <Line type="monotone" dataKey="nodeClient" stroke="#82ca9d" />
          </LineChart>
        </div>
        <div>
          <h2>Slow Queries</h2>
          <LineChart width={400} height={300} data={slowQueryData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="time" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="count" stroke="#8884d8" />
          </LineChart>
        </div>
        {dockerPythonData && (
          <div>
            <h2>Python Docker Container</h2>
            <LineChart width={400} height={300} data={dockerPythonData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="cpu_percent" stroke="#8884d8" />
              <Line type="monotone" dataKey="mem_percent" stroke="#82ca9d" />
            </LineChart>
          </div>
        )}
        {dockerMongodbData && (
          <div>
            <h2>MongoDB Docker Container</h2>
            <LineChart width={400} height={300} data={dockerMongodbData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="cpu_percent" stroke="#8884d8" />
              <Line type="monotone" dataKey="mem_percent" stroke="#82ca9d" />
            </LineChart>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
