package ${package};

import org.apache.ibatis.annotations.*;
import java.util.List;

@Mapper
public interface ${ClassName}Mapper {

    @Select("SELECT * FROM ${table_name} WHERE deleted = 0")
    List<${ClassName}DTO> list();

    @Select("SELECT * FROM ${table_name} WHERE id = #{id} AND deleted = 0")
    ${ClassName}DTO getById(Long id);

    @Insert("INSERT INTO ${table_name} (...) VALUES (...)")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    void create(${ClassName}DTO dto);

    @Update("UPDATE ${table_name} SET ... WHERE id = #{id}")
    void update(${ClassName}DTO dto);

    @Update("UPDATE ${table_name} SET deleted = 1 WHERE id = #{id}")
    void delete(Long id);
}
