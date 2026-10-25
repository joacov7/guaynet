import { useEffect, useState } from "react";
import {
  Button,
  Col,
  DatePicker,
  Form,
  Input,
  InputNumber,
  Modal,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import {
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import { expensesApi } from "@/services/api";
import type { Expense, ExpenseCategory } from "@/types";

const { Title } = Typography;
const { Option } = Select;
const { RangePicker } = DatePicker;

const CATEGORY_LABELS: Record<ExpenseCategory, string> = {
  hosting: "Hosting",
  equipment: "Equipos",
  energy: "Energía",
  labor: "Mano de obra",
  internet: "Internet",
  transport: "Transporte",
  software: "Software",
  maintenance: "Mantenimiento",
  other: "Otro",
};

const CATEGORY_COLORS: Record<ExpenseCategory, string> = {
  hosting: "blue",
  equipment: "purple",
  energy: "orange",
  labor: "green",
  internet: "cyan",
  transport: "gold",
  software: "geekblue",
  maintenance: "magenta",
  other: "default",
};

const CATEGORIES: ExpenseCategory[] = [
  "hosting", "equipment", "energy", "labor", "internet",
  "transport", "software", "maintenance", "other",
];

function fmt(v: number) {
  return `$${v.toLocaleString("es-AR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function Expenses() {
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [loading, setLoading] = useState(false);
  const [filterCategory, setFilterCategory] = useState<ExpenseCategory | undefined>();
  const [filterDates, setFilterDates] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null);

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Expense | null>(null);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();

  const [summary, setSummary] = useState<{ total: number; by_category: Record<string, number> } | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (filterCategory) params.category = filterCategory;
      if (filterDates) {
        params.date_from = filterDates[0].format("YYYY-MM-DD");
        params.date_to = filterDates[1].format("YYYY-MM-DD");
      }
      const [data, sum] = await Promise.all([
        expensesApi.list(params as never),
        expensesApi.summary(
          filterDates
            ? { year: filterDates[0].year() }
            : { year: new Date().getFullYear() }
        ),
      ]);
      setExpenses(data);
      setSummary(sum);
    } catch {
      message.error("Error al cargar gastos");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [filterCategory, filterDates]);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ expense_date: dayjs(), category: "other" });
    setModalOpen(true);
  };

  const openEdit = (r: Expense) => {
    setEditing(r);
    form.setFieldsValue({
      ...r,
      expense_date: dayjs(r.expense_date),
    });
    setModalOpen(true);
  };

  const handleSave = async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      const payload = {
        ...values,
        expense_date: (values.expense_date as dayjs.Dayjs).format("YYYY-MM-DD"),
      };
      if (editing) {
        await expensesApi.update(editing.id, payload);
        message.success("Gasto actualizado");
      } else {
        await expensesApi.create(payload);
        message.success("Gasto creado");
      }
      setModalOpen(false);
      load();
    } catch {
      message.error("Error al guardar");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    Modal.confirm({
      title: "¿Eliminar gasto?",
      okText: "Eliminar",
      okType: "danger",
      cancelText: "Cancelar",
      onOk: async () => {
        try {
          await expensesApi.delete(id);
          message.success("Gasto eliminado");
          load();
        } catch {
          message.error("Error al eliminar");
        }
      },
    });
  };

  const columns: ColumnsType<Expense> = [
    {
      title: "Fecha",
      dataIndex: "expense_date",
      width: 110,
      render: (v: string) => dayjs(v).format("DD/MM/YYYY"),
      sorter: (a, b) => a.expense_date.localeCompare(b.expense_date),
      defaultSortOrder: "descend",
    },
    {
      title: "Descripción",
      dataIndex: "description",
      ellipsis: true,
    },
    {
      title: "Categoría",
      dataIndex: "category",
      width: 140,
      render: (v: ExpenseCategory) => (
        <Tag color={CATEGORY_COLORS[v]}>{CATEGORY_LABELS[v]}</Tag>
      ),
    },
    {
      title: "Proveedor",
      dataIndex: "vendor",
      width: 150,
      ellipsis: true,
      render: (v: string | null) => v || "—",
    },
    {
      title: "Monto",
      dataIndex: "amount",
      width: 120,
      align: "right",
      render: (v: number) => fmt(v),
      sorter: (a, b) => a.amount - b.amount,
    },
    {
      title: "",
      key: "actions",
      width: 80,
      render: (_: unknown, r: Expense) => (
        <Space size={4}>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)} />
          <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDelete(r.id)} />
        </Space>
      ),
    },
  ];

  const total = expenses.reduce((s, e) => s + e.amount, 0);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>Gastos</Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={load} loading={loading} />
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            Nuevo gasto
          </Button>
        </Space>
      </div>

      {/* Summary cards */}
      {summary && (
        <Row gutter={12} style={{ marginBottom: 16 }}>
          <Col>
            <Statistic title="Total filtrado" value={total} formatter={(v) => fmt(Number(v))} />
          </Col>
          <Col>
            <Statistic
              title={`Total año ${new Date().getFullYear()}`}
              value={summary.total}
              formatter={(v) => fmt(Number(v))}
            />
          </Col>
          {Object.entries(summary.by_category)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 4)
            .map(([cat, val]) => (
              <Col key={cat}>
                <Statistic
                  title={CATEGORY_LABELS[cat as ExpenseCategory] ?? cat}
                  value={val}
                  formatter={(v) => fmt(Number(v))}
                />
              </Col>
            ))}
        </Row>
      )}

      {/* Filters */}
      <Space style={{ marginBottom: 12 }} wrap>
        <Select
          allowClear
          placeholder="Todas las categorías"
          style={{ width: 200 }}
          value={filterCategory}
          onChange={setFilterCategory}
        >
          {CATEGORIES.map((c) => (
            <Option key={c} value={c}>{CATEGORY_LABELS[c]}</Option>
          ))}
        </Select>
        <RangePicker
          value={filterDates}
          onChange={(v) => setFilterDates(v as [dayjs.Dayjs, dayjs.Dayjs] | null)}
          format="DD/MM/YYYY"
        />
      </Space>

      <Table
        rowKey="id"
        columns={columns}
        dataSource={expenses}
        loading={loading}
        size="small"
        pagination={{ pageSize: 50, showSizeChanger: true }}
        summary={() => (
          <Table.Summary.Row>
            <Table.Summary.Cell index={0} colSpan={4} />
            <Table.Summary.Cell index={4} align="right">
              <strong>{fmt(total)}</strong>
            </Table.Summary.Cell>
            <Table.Summary.Cell index={5} />
          </Table.Summary.Row>
        )}
      />

      <Modal
        open={modalOpen}
        title={editing ? "Editar gasto" : "Nuevo gasto"}
        onCancel={() => setModalOpen(false)}
        onOk={handleSave}
        okText={editing ? "Guardar" : "Crear"}
        confirmLoading={saving}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 8 }}>
          <Form.Item name="description" label="Descripción" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="amount" label="Monto ($)" rules={[{ required: true }]}>
                <InputNumber min={0} step={0.01} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="expense_date" label="Fecha" rules={[{ required: true }]}>
                <DatePicker style={{ width: "100%" }} format="DD/MM/YYYY" />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="category" label="Categoría" rules={[{ required: true }]}>
                <Select>
                  {CATEGORIES.map((c) => (
                    <Option key={c} value={c}>{CATEGORY_LABELS[c]}</Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="vendor" label="Proveedor">
                <Input />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="invoice_number" label="Nro. comprobante">
            <Input />
          </Form.Item>
          <Form.Item name="notes" label="Notas">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
