package ${package};

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import lombok.RequiredArgsConstructor;
import java.util.List;

@Service
@RequiredArgsConstructor
public class ${ClassName}Service {

    private final ${ClassName}Mapper ${className}Mapper;

    public List<${ClassName}DTO> list() {
        return ${className}Mapper.list();
    }

    public ${ClassName}DTO getById(Long id) {
        return ${className}Mapper.getById(id);
    }

    @Transactional
    public ${ClassName}DTO create(${ClassName}DTO dto) {
        ${className}Mapper.create(dto);
        return dto;
    }

    @Transactional
    public ${ClassName}DTO update(Long id, ${ClassName}DTO dto) {
        dto.setId(id);
        ${className}Mapper.update(dto);
        return dto;
    }

    @Transactional
    public void delete(Long id) {
        ${className}Mapper.delete(id);
    }
}
