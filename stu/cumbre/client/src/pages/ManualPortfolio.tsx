import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { manualApi, fundsApi } from '../api/client';
import { Briefcase, TrendingUp, DollarSign, ChevronDown, ChevronUp, Info, ArrowRight } from 'lucide-react';

export default function ManualPortfolio() {
  const navigate = useNavigate();
  const [portfolios, setPortfolios] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [fundNames, setFundNames] = useState<Record<string, string>>({});

  useEffect(() => {
    manualApi.listPortfolios()
      .then(async (res) => {
        setPortfolios(res.data);
        const codes: string[] = [];
        for (const p of res.data) {
          p.positions?.forEach((pos: any) => codes.push(pos.fund_code));
          p.trades?.forEach((t: any) => codes.push(t.fund_code));
        }
        if (codes.length) {
          const names = await fundsApi.names(codes);
          setFundNames(names);
        }
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" /></div>;

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-800">手动组合</h1>
        <p className="text-gray-500 mt-1">追踪手动决策的持仓和收益表现</p>
      </div>

      {/* Info Banner */}
      <div className="card bg-blue-50 border-blue-200 mb-6">
        <div className="flex items-start gap-3">
          <Info size={20} className="text-blue-600 mt-0.5 shrink-0" />
          <div>
            <p className="font-medium text-blue-800">什么是手动组合？</p>
            <p className="text-sm text-blue-700 mt-1">
              在执行清单（跟投清单）中，你可以手动增删改买入/卖出项目，确认提交后系统将根据你的决策生成对应的投资组合。
              这里展示你所有手动创建的组合，包括持仓明细和交易记录，方便你追踪手动决策的收益表现。
            </p>
            <button
              onClick={() => navigate('/manual')}
              className="mt-2 inline-flex items-center gap-1 text-sm font-medium text-blue-700 hover:text-blue-800"
            >
              去执行清单 <ArrowRight size={14} />
            </button>
          </div>
        </div>
      </div>

      {portfolios.length === 0 ? (
        <div className="card text-center py-12">
          <Briefcase size={48} className="mx-auto text-gray-300 mb-3" />
          <p className="text-gray-400">暂无手动组合</p>
          <p className="text-gray-400 text-sm mt-1">在执行清单中确认操作后，组合将自动创建</p>
          <button
            onClick={() => navigate('/manual')}
            className="mt-4 btn-primary inline-flex items-center gap-2"
          >
            去执行清单 <ArrowRight size={16} />
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {portfolios.map(p => {
            const isOpen = expanded === p.id;
            return (
              <div key={p.id} className="card">
                <div className="flex items-center justify-between cursor-pointer" onClick={() => setExpanded(isOpen ? null : p.id)}>
                  <div className="flex items-center gap-3">
                    <Briefcase size={20} className="text-primary-500" />
                    <div>
                      <h2 className="font-semibold text-gray-800">{p.name}</h2>
                      <div className="flex items-center gap-4 text-sm text-gray-500 mt-1">
                        <span className="flex items-center gap-1"><TrendingUp size={14} /> 投入 ¥{p.total_invested?.toLocaleString()}</span>
                        <span className="flex items-center gap-1"><DollarSign size={14} /> 现金 ¥{p.cash?.toLocaleString()}</span>
                      </div>
                    </div>
                  </div>
                  {isOpen ? <ChevronUp size={20} className="text-gray-400" /> : <ChevronDown size={20} className="text-gray-400" />}
                </div>

                {isOpen && (
                  <div className="mt-4 pt-4 border-t space-y-6">
                    {/* Positions */}
                    <div>
                      <h3 className="text-sm font-medium text-gray-500 mb-3">持仓</h3>
                      {p.positions?.length === 0 ? (
                        <p className="text-gray-400 text-sm">暂无持仓</p>
                      ) : (
                        <table className="w-full">
                          <thead>
                            <tr className="border-b text-left text-sm text-gray-500">
                              <th className="px-4 py-2 font-medium">基金</th>
                              <th className="px-4 py-2 font-medium">份额</th>
                              <th className="px-4 py-2 font-medium">成本净值</th>
                            </tr>
                          </thead>
                          <tbody>
                            {p.positions?.map((pos: any) => (
                              <tr key={pos.id} className="border-b last:border-0">
                                <td className="px-4 py-2 text-sm">
                                  <span className="font-mono text-primary-600">{pos.fund_code}</span>
                                  {fundNames[pos.fund_code] && <span className="text-gray-500 ml-2">{fundNames[pos.fund_code]}</span>}
                                </td>
                                <td className="px-4 py-2 text-sm text-gray-700">{pos.shares?.toFixed(2)}</td>
                                <td className="px-4 py-2 text-sm text-gray-600">{pos.cost_nav?.toFixed(4)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )}
                    </div>

                    {/* Trades */}
                    <div>
                      <h3 className="text-sm font-medium text-gray-500 mb-3">交易记录</h3>
                      {p.trades?.length === 0 ? (
                        <p className="text-gray-400 text-sm">暂无交易</p>
                      ) : (
                        <table className="w-full">
                          <thead>
                            <tr className="border-b text-left text-sm text-gray-500">
                              <th className="px-4 py-2 font-medium">日期</th>
                              <th className="px-4 py-2 font-medium">基金</th>
                              <th className="px-4 py-2 font-medium">类型</th>
                              <th className="px-4 py-2 font-medium">金额</th>
                              <th className="px-4 py-2 font-medium">净值</th>
                            </tr>
                          </thead>
                          <tbody>
                            {p.trades?.map((t: any) => (
                              <tr key={t.id} className="border-b last:border-0">
                                <td className="px-4 py-2 text-sm text-gray-500">{t.date}</td>
                                <td className="px-4 py-2 text-sm">
                                  <span className="font-mono text-primary-600">{t.fund_code}</span>
                                  {fundNames[t.fund_code] && <span className="text-gray-500 ml-2">{fundNames[t.fund_code]}</span>}
                                </td>
                                <td className="px-4 py-2">
                                  <span className={`text-xs px-2 py-1 rounded-full font-medium ${t.type === 'buy' ? 'text-green-600 bg-green-50' : 'text-red-600 bg-red-50'}`}>
                                    {t.type === 'buy' ? '买入' : '卖出'}
                                  </span>
                                </td>
                                <td className="px-4 py-2 text-sm text-gray-700">¥{t.amount?.toLocaleString()}</td>
                                <td className="px-4 py-2 text-sm text-gray-500">{t.nav?.toFixed(4)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
