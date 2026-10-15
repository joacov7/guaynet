import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Input, Select, Card, Row, Col, Typography, Spin, Empty, Avatar } from "antd";
import { SearchOutlined, PlayCircleOutlined } from "@ant-design/icons";
import Hls from "hls.js";
import { watchApi, Channel, Category } from "../services/api";

const { Title, Text } = Typography;

function Player({ channel }: { channel: Channel | null }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const hlsRef = useRef<Hls | null>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !channel) return;

    if (hlsRef.current) {
      hlsRef.current.destroy();
      hlsRef.current = null;
    }

    if (Hls.isSupported()) {
      const hls = new Hls({ enableWorker: true });
      hlsRef.current = hls;
      hls.loadSource(channel.stream_url);
      hls.attachMedia(video);
      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        video.play().catch(() => undefined);
      });
    } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = channel.stream_url;
      video.play().catch(() => undefined);
    }

    return () => {
      hlsRef.current?.destroy();
      hlsRef.current = null;
    };
  }, [channel]);

  if (!channel) {
    return (
      <div style={{ height: 360, display: "flex", alignItems: "center", justifyContent: "center", background: "#000", borderRadius: 8 }}>
        <PlayCircleOutlined style={{ fontSize: 64, color: "#555" }} />
      </div>
    );
  }

  return (
    <div>
      <video
        ref={videoRef}
        controls
        style={{ width: "100%", maxHeight: 480, borderRadius: 8, background: "#000" }}
      />
      <Title level={4} style={{ color: "#fff", marginTop: 12 }}>
        {channel.name}
      </Title>
    </div>
  );
}

export default function Watch() {
  const [selectedChannel, setSelectedChannel] = useState<Channel | null>(null);
  const [categoryId, setCategoryId] = useState<number | undefined>();
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");

  const { data: categories = [] } = useQuery({
    queryKey: ["categories"],
    queryFn: () => watchApi.categories().then((r) => r.data),
  });

  const { data: channels = [], isLoading } = useQuery({
    queryKey: ["channels", categoryId, search],
    queryFn: () => watchApi.channels({ category_id: categoryId, search: search || undefined }).then((r) => r.data),
  });

  const categoryOptions: { value: number | undefined; label: string }[] = [
    { value: undefined, label: "Todas" },
    ...categories.map((c: Category) => ({ value: c.id, label: c.name })),
  ];

  return (
    <div style={{ background: "#0a0a0a", minHeight: "100vh", padding: 24 }}>
      <Row gutter={24}>
        <Col xs={24} lg={14} xl={16}>
          <Player channel={selectedChannel} />
        </Col>
        <Col xs={24} lg={10} xl={8}>
          <div style={{ marginBottom: 12, display: "flex", gap: 8 }}>
            <Select
              style={{ width: 160 }}
              value={categoryId}
              onChange={setCategoryId}
              options={categoryOptions}
            />
            <Input
              prefix={<SearchOutlined />}
              placeholder="Buscar canal..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onPressEnter={() => setSearch(searchInput)}
              allowClear
              onClear={() => { setSearch(""); setSearchInput(""); }}
            />
          </div>
          <div style={{ height: "calc(100vh - 180px)", overflowY: "auto" }}>
            {isLoading ? (
              <div style={{ textAlign: "center", padding: 40 }}>
                <Spin />
              </div>
            ) : channels.length === 0 ? (
              <Empty description={<Text style={{ color: "#888" }}>Sin canales</Text>} />
            ) : (
              <Row gutter={[8, 8]}>
                {channels.map((ch: Channel) => (
                  <Col xs={12} sm={8} md={6} lg={12} xl={8} key={ch.id}>
                    <Card
                      hoverable
                      onClick={() => setSelectedChannel(ch)}
                      style={{
                        background: selectedChannel?.id === ch.id ? "#1677ff22" : "#141414",
                        border: selectedChannel?.id === ch.id ? "1px solid #1677ff" : "1px solid #303030",
                        cursor: "pointer",
                        textAlign: "center",
                      }}
                      styles={{ body: { padding: "12px 8px" } }}
                    >
                      {ch.logo_url ? (
                        <Avatar src={ch.logo_url} size={40} style={{ marginBottom: 6 }} />
                      ) : (
                        <Avatar size={40} style={{ marginBottom: 6, background: "#1677ff" }}>
                          {ch.name[0]}
                        </Avatar>
                      )}
                      <Text ellipsis style={{ color: "#fff", fontSize: 12, display: "block" }}>
                        {ch.name}
                      </Text>
                    </Card>
                  </Col>
                ))}
              </Row>
            )}
          </div>
        </Col>
      </Row>
    </div>
  );
}
