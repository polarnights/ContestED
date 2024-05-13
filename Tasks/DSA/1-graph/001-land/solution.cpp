#include <vector>
#include <string>

class Solution
{
private:
    std::vector<std::vector<bool>> visited;
    int n;
    int m;

public:
    void dfs(std::vector<std::vector<char>> &grid, int idx_i, int idx_j)
    {
        visited[idx_i][idx_j] = 1;
        if (idx_i < m - 1 && grid[idx_i + 1][idx_j] == 'W' &&
            !visited[idx_i + 1][idx_j])
        {
            dfs(grid, idx_i + 1, idx_j);
        }
        if (idx_j < n - 1 && grid[idx_i][idx_j + 1] == 'W' &&
            !visited[idx_i][idx_j + 1])
        {
            dfs(grid, idx_i, idx_j + 1);
        }
        if (idx_j > 0 && grid[idx_i][idx_j - 1] == 'W' &&
            !visited[idx_i][idx_j - 1])
        {
            dfs(grid, idx_i, idx_j - 1);
        }
        if (idx_i > 0 && grid[idx_i - 1][idx_j] == 'W' &&
            !visited[idx_i - 1][idx_j])
        {
            dfs(grid, idx_i - 1, idx_j);
        }
    }

    int numIslands(std::vector<std::vector<char>> &grid)
    {
        if (grid.empty())
        {
            return 0;
        }
        m = grid.size();
        n = grid[0].size();
        int result = 0;
        visited.resize(m);
        for (auto &elem : visited)
        {
            elem.resize(n, 0);
        }
        for (int i = 0; i < m; i++)
        {
            for (int j = 0; j < n; j++)
            {
                if (grid[i][j] == 'W' && !visited[i][j])
                {
                    dfs(grid, i, j);
                    result++;
                }
            }
        }
        return result;
    }
};