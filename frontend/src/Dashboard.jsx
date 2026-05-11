import { useState, useEffect } from "react"
import API_URL from "./api"

function Dashboard({ token, onBack }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")



  const fetchDashboard = async () => {
    try {
      const res = await fetch(`${API_URL}/dashboard`, {
        headers: { "Authorization": `Bearer ${token}` }
      })
      const json = await res.json()
      if (!res.ok) {
        setError(json.detail || "데이터 불러오기 실패")
        return
      }
      setData(json)
    } catch (e) {
      void e
      setError("서버 연결 실패")
    } finally {
      setLoading(false)
    }
  }

    useEffect(() => {
        fetchDashboard()
     }, [ ])

  if (loading) return (
    <div style={styles.center}>
      <p>📊 데이터 불러오는 중...</p>
    </div>
  )

  if (error) return (
    <div style={styles.center}>
      <p style={{ color: "red" }}>{error}</p>
    </div>
  )

  const passRate = data.total > 0
    ? Math.round((data.pass_count / data.total) * 100)
    : 0

  return (
    <div style={styles.container}>
      {/* 헤더 */}
      <div style={styles.header}>
        <div>
          <h1 style={styles.headerTitle}>📊 로그 분석 대시보드</h1>
          <p style={styles.headerSubtitle}>IT 보안 정책 RAG 시스템 사용 현황</p>
        </div>
        <button style={styles.backButton} onClick={onBack}>
          ← 챗봇으로 돌아가기
        </button>
      </div>

      <div style={styles.content}>
        {/* 통계 카드 */}
        <div style={styles.cardRow}>
          <div style={styles.card}>
            <p style={styles.cardLabel}>총 질문 수</p>
            <p style={styles.cardValue}>{data.total}</p>
          </div>
          <div style={{...styles.card, backgroundColor: "#f6ffed", borderColor: "#b7eb8f"}}>
            <p style={styles.cardLabel}>✅ PASS</p>
            <p style={{...styles.cardValue, color: "#52c41a"}}>{data.pass_count}</p>
          </div>
          <div style={{...styles.card, backgroundColor: "#fff2f0", borderColor: "#ffccc7"}}>
            <p style={styles.cardLabel}>❌ FAIL</p>
            <p style={{...styles.cardValue, color: "#ff4d4f"}}>{data.fail_count}</p>
          </div>
          <div style={{...styles.card, backgroundColor: "#e6f7ff", borderColor: "#91d5ff"}}>
            <p style={styles.cardLabel}>PASS 비율</p>
            <p style={{...styles.cardValue, color: "#1890ff"}}>{passRate}%</p>
          </div>
        </div>

        <div style={styles.row}>
          {/* 질문 유형별 통계 */}
          <div style={styles.section}>
            <h2 style={styles.sectionTitle}>🏷️ 질문 유형별 통계</h2>
            {Object.entries(data.type_stats).length === 0 ? (
              <p style={styles.empty}>데이터 없음</p>
            ) : (
              Object.entries(data.type_stats).map(([type, count]) => (
                <div key={type} style={styles.statRow}>
                  <span style={styles.statLabel}>
                    {type === "ACTION" ? "🔧 ACTION" :
                     type === "POLICY" ? "📋 POLICY" :
                     type === "DEFINITION" ? "📖 DEFINITION" : type}
                  </span>
                  <div style={styles.barWrap}>
                    <div style={{
                      ...styles.bar,
                      width: `${Math.round((count / data.total) * 100)}%`
                    }} />
                  </div>
                  <span style={styles.statCount}>{count}건</span>
                </div>
              ))
            )}
          </div>

          {/* 사용자별 통계 */}
          <div style={styles.section}>
            <h2 style={styles.sectionTitle}>👤 사용자별 질문 수</h2>
            {data.user_stats.length === 0 ? (
              <p style={styles.empty}>데이터 없음</p>
            ) : (
              data.user_stats.map((u, idx) => (
                <div key={idx} style={styles.statRow}>
                  <span style={styles.statLabel}>
                    {idx === 0 ? "🥇" : idx === 1 ? "🥈" : idx === 2 ? "🥉" : "👤"} {u.username}
                  </span>
                  <div style={styles.barWrap}>
                    <div style={{
                      ...styles.bar,
                      width: `${Math.round((u.count / data.user_stats[0].count) * 100)}%`,
                      backgroundColor: "#722ed1"
                    }} />
                  </div>
                  <span style={styles.statCount}>{u.count}건</span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* 최근 질문 목록 */}
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>📋 최근 질문 목록</h2>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>질문</th>
                <th style={styles.th}>유형</th>
                <th style={styles.th}>검증</th>
                <th style={styles.th}>시간</th>
              </tr>
            </thead>
            <tbody>
              {data.recent_logs.map((log, idx) => (
                <tr key={idx} style={idx % 2 === 0 ? styles.trEven : styles.trOdd}>
                  <td style={styles.td}>{log.question}</td>
                  <td style={{...styles.td, textAlign: "center"}}>
                    <span style={styles.tag}>{log.question_type}</span>
                  </td>
                  <td style={{...styles.td, textAlign: "center"}}>
                    {log.is_valid ? "✅" : "❌"}
                  </td>
                  <td style={{...styles.td, fontSize: "11px", color: "#888"}}>
                    {log.created_at.slice(0, 16)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

const styles = {
  container: {
    minHeight: "100vh",
    backgroundColor: "#f5f5f5",
    fontFamily: "sans-serif"
  },
  center: {
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    height: "100vh",
    fontSize: "16px"
  },
  header: {
    backgroundColor: "#1a1a2e",
    color: "white",
    padding: "16px 24px",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center"
  },
  headerTitle: {
    margin: 0,
    fontSize: "20px",
    color: "#ffffff"
  },
  headerSubtitle: {
    margin: "4px 0 0",
    fontSize: "12px",
    opacity: 0.7
  },
  backButton: {
    padding: "8px 16px",
    backgroundColor: "transparent",
    color: "white",
    border: "1px solid rgba(255,255,255,0.3)",
    borderRadius: "8px",
    fontSize: "13px",
    cursor: "pointer"
  },
  content: {
    maxWidth: "1000px",
    margin: "0 auto",
    padding: "24px"
  },
  cardRow: {
    display: "flex",
    gap: "16px",
    marginBottom: "24px"
  },
  card: {
    flex: 1,
    backgroundColor: "white",
    border: "1px solid #ddd",
    borderRadius: "12px",
    padding: "20px",
    textAlign: "center"
  },
  cardLabel: {
    margin: "0 0 8px",
    fontSize: "13px",
    color: "#888"
  },
  cardValue: {
    margin: 0,
    fontSize: "32px",
    fontWeight: "bold",
    color: "#1a1a2e"
  },
  row: {
    display: "flex",
    gap: "16px",
    marginBottom: "24px"
  },
  section: {
    flex: 1,
    backgroundColor: "white",
    borderRadius: "12px",
    padding: "20px",
    boxShadow: "0 1px 4px rgba(0,0,0,0.08)"
  },
  sectionTitle: {
    margin: "0 0 16px",
    fontSize: "16px",
    color: "#1a1a2e"
  },
  empty: {
    color: "#aaa",
    fontSize: "13px"
  },
  statRow: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    marginBottom: "12px"
  },
  statLabel: {
    width: "120px",
    fontSize: "13px",
    color: "#333"
  },
  barWrap: {
    flex: 1,
    backgroundColor: "#f0f0f0",
    borderRadius: "4px",
    height: "12px",
    overflow: "hidden"
  },
  bar: {
    height: "100%",
    backgroundColor: "#1a1a2e",
    borderRadius: "4px",
    transition: "width 0.3s"
  },
  statCount: {
    width: "40px",
    fontSize: "13px",
    color: "#666",
    textAlign: "right"
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: "13px"
  },
  th: {
    padding: "10px 12px",
    backgroundColor: "#f5f5f5",
    color: "#666",
    fontWeight: "bold",
    textAlign: "left",
    borderBottom: "1px solid #eee"
  },
  td: {
    padding: "10px 12px",
    borderBottom: "1px solid #f0f0f0",
    color: "#333"
  },
  trEven: {
    backgroundColor: "white"
  },
  trOdd: {
    backgroundColor: "#fafafa"
  },
  tag: {
    padding: "2px 8px",
    backgroundColor: "#e6f7ff",
    color: "#1890ff",
    borderRadius: "10px",
    fontSize: "11px"
  }
}

export default Dashboard